from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import sys
import os
from pathlib import Path
import time
import logging

# Add search module to path
search_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'search')
if search_path not in sys.path:
    sys.path.append(search_path)

# Import Meilisearch service
from search.meili_search_service import meili_search_service as search_service
SEARCH_ENGINE = "Meilisearch"

from .models import Query, Answer, QuerySession, TeamAnswer
from .serializers import (
    QuerySerializer, AnswerSerializer, QueryCreateSerializer, 
    QueryUpdateSerializer, AnswerCreateSerializer, QuerySessionSerializer,
    TeamAnswerSerializer, TeamAnswerCreateSerializer
)

class QueryListCreateAPIView(APIView):
    """
    API endpoint for listing and creating queries
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_summary="List all queries",
        operation_description="Get a paginated list of all queries with optional filtering",
        manual_parameters=[
            openapi.Parameter('search', openapi.IN_QUERY, description="Search in text, ocr, speech fields", type=openapi.TYPE_STRING),
            openapi.Parameter('session', openapi.IN_QUERY, description="Filter by session ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Filter by start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="Filter by end date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('viewmode', openapi.IN_QUERY, description="View mode for frames: 'gallery' (flat list) or 'samevideo' (grouped by video)", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Queries retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'frames': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="Frame data structure depends on viewmode parameter. Gallery mode returns flat array, samevideo mode returns 2D array where each element is an array of frames from the same video.",
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                description="Frame object or array of frame objects (depends on viewmode)",
                                properties={
                                    'url': openapi.Schema(type=openapi.TYPE_STRING, description="Full URL to frame image"),
                                    'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Video name"),
                                    'frame_index': openapi.Schema(type=openapi.TYPE_STRING, description="Frame index"),
                                }
                            )
                        ),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pages': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            )
        }
    )
    def get(self, request):
        """Get all queries with filtering and pagination"""
        queryset = Query.objects.all()
        
        # Apply filters
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(text__icontains=search) |
                Q(ocr__icontains=search) |
                Q(speech__icontains=search)
            )
        
        # Filter by session
        session_id = request.query_params.get('session')
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(time__gte=start_date)
        if end_date:
            queryset = queryset.filter(time__lte=end_date)
        
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page_number = int(request.query_params.get('page', 1))
        
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        
        serializer = QuerySerializer(page.object_list, many=True, context={'request': request})
        
        # Search frames for the latest query if it exists and has OCR data
        frames = []
        if page.object_list:
            # Get the most recent query from the current page
            latest_query = page.object_list[0]  # Already ordered by -created_at
            
            # Perform OCR search on the latest query if it has OCR data
            if latest_query.ocr:
                total_start = time.time()
                
                print(f"Starting OCR search for latest query: '{latest_query.ocr}'")
                ocr_results = self._search_ocr(latest_query.ocr)
                print("result[0]:", ocr_results[0] if ocr_results else "No results found")
                raw_frames = self.adjust_response(request, ocr_results)
                
                # Process frames based on viewmode
                viewmode = request.query_params.get('viewmode', 'gallery')
                print(f"Processing frames with viewmode: {viewmode}")
                frames = self._process_frames_by_viewmode(raw_frames, viewmode)
                print(f"Processed frames count: {len(frames)}")
                if viewmode == 'samevideo' and frames:
                    print(f"Video groups: {len(frames)}, first group frames: {len(frames[0]) if frames[0] else 0}")
                elif viewmode == 'gallery':
                    print(f"Gallery frames: {len(frames)}")
                
                total_end = time.time()
                total_duration = total_end - total_start
                
                print(f"Total OCR process time: {total_duration:.3f} seconds")
        
        return Response({
            'message': 'Queries retrieved successfully',
            'data': serializer.data,
            'frames': frames,  # Add frames to response
            'total': paginator.count,
            'page': page_number,
            'pages': paginator.num_pages
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create a new query",
        operation_description="Create a new query with optional image upload.",
        request_body=QueryCreateSerializer,
        responses={
            201: openapi.Response(
                description="Query created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'text': openapi.Schema(type=openapi.TYPE_STRING),
                                'ocr': openapi.Schema(type=openapi.TYPE_STRING),
                                'speech': openapi.Schema(type=openapi.TYPE_STRING),
                                'image': openapi.Schema(type=openapi.TYPE_STRING),
                                'time': openapi.Schema(type=openapi.TYPE_STRING),
                                'background_sound': openapi.Schema(type=openapi.TYPE_STRING),
                                'stage': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                    }
                )
            ),
            400: openapi.Response(description="Validation error")
        }
    )
    def post(self, request):
        """Create a new query"""
        serializer = QueryCreateSerializer(data=request.data)
        if serializer.is_valid():
            query = serializer.save()
            
            response_serializer = QuerySerializer(query, context={'request': request})
            
            return Response({
                'message': 'Query created successfully',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Failed to create query',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def _search_ocr(self, ocr_text: str) -> list:
        """
        Perform OCR search using sync method
        
        Args:
            ocr_text: OCR text to search for
            
        Returns:
            List of search results or empty list if error
        """
        try:
            search_start = time.time()
            print(f"Starting OCR search for: '{ocr_text}' using {SEARCH_ENGINE}")
            
            # Sử dụng sync method 
            results = search_service.search_ocr(ocr_text, size=300)
            
            search_end = time.time()
            search_duration = search_end - search_start
            print(f"{SEARCH_ENGINE} search took {search_duration:.3f} seconds")
            
            return results
            
        except Exception as e:
            # Log error but don't fail the request
            print(f"OCR search error: {e}")
            return []

    def adjust_response(self, request, results: list) -> list:
        """
        Adjust OCR search results to create frames array with full URLs
        
        Args:
            request: Django request object
            results: List of OCR search results, each containing video_name and frame_index
            
        Returns:
            List of frames with url, video_name, frame_index
        """
        if not results:
            return []
        
        # Get SERVER_IP from environment, fallback to request host
        server_ip = os.environ.get('SERVER_IP')
        if server_ip:
            base_url = f"http://{server_ip}"
        else:
            # Fallback to request host
            host = request.get_host()
            scheme = 'https' if request.is_secure() else 'http'
            base_url = f"{scheme}://{host}"
        
        frames = []
        for result in results:
            video_name = result.get('video_name', '')
            frame_index = result.get('frame_index', '')
            
            # Build frame URL: http://{SERVER_IP}/media/keyframes/{video_name}/{frame_index}.jpg
            frame_url = f"{base_url}/media/frames/{video_name}/{frame_index}.jpg"
            
            frame_data = {
                'url': frame_url,
                'video_name': video_name,
                'frame_index': frame_index
            }
            frames.append(frame_data)
        
        return frames
    
    def _process_frames_by_viewmode(self, frames: list, viewmode: str) -> list:
        """
        Process frames based on viewmode
        
        Args:
            frames: List of frame data
            viewmode: 'gallery' or 'samevideo'
            
        Returns:
            Processed frames based on viewmode:
            - 'gallery': Returns a flat array (1D) of frames
            - 'samevideo': Returns a 2D array where each element is an array of frames from the same video
        """
        if viewmode == 'samevideo':
            # Group frames by video_name
            video_groups = {}
            for frame in frames:
                video_name = frame.get('video_name', '')
                if video_name not in video_groups:
                    video_groups[video_name] = []
                video_groups[video_name].append(frame)
            
            # Convert to 2D array - each element is an array of frames from the same video
            result = []
            for video_name, video_frames in video_groups.items():
                # Sort frames by frame_index within each video
                sorted_frames = sorted(video_frames, key=lambda x: int(x.get('frame_index', 0)))
                result.append(sorted_frames)
            
            # Sort video groups by the first frame's video name for consistency
            result.sort(key=lambda x: x[0].get('video_name', '') if x else '')
            
            return result
        else:
            # Gallery mode - return frames as flat list (1D array)
            return frames

    # ...existing code...


class QueryDetailAPIView(APIView):
    """
    API endpoint for retrieving, updating and deleting a specific query
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        """Helper method to get query object"""
        return get_object_or_404(Query, pk=pk)

    @swagger_auto_schema(
        operation_summary="Get query details",
        operation_description="Retrieve details of a specific query by ID",
        responses={
            200: openapi.Response(
                description="Query retrieved successfully",
                schema=QuerySerializer
            ),
            404: openapi.Response(description="Query not found")
        }
    )
    def get(self, request, pk):
        """Get a specific query"""
        query = self.get_object(pk)
        serializer = QuerySerializer(query, context={'request': request})
        return Response({
            'message': 'Query retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Update query",
        operation_description="Update an existing query (full update)",
        request_body=QueryUpdateSerializer,
        responses={
            200: openapi.Response(description="Query updated successfully"),
            400: openapi.Response(description="Validation error"),
            404: openapi.Response(description="Query not found")
        }
    )
    def put(self, request, pk):
        """Update a query (full update)"""
        query = self.get_object(pk)
        serializer = QueryUpdateSerializer(query, data=request.data)
        
        if serializer.is_valid():
            updated_query = serializer.save()
            response_serializer = QuerySerializer(updated_query, context={'request': request})
            return Response({
                'message': 'Query updated successfully',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Failed to update query',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Partially update query",
        operation_description="Partially update an existing query",
        request_body=QueryUpdateSerializer,
        responses={
            200: openapi.Response(description="Query updated successfully"),
            400: openapi.Response(description="Validation error"),
            404: openapi.Response(description="Query not found")
        }
    )
    def patch(self, request, pk):
        """Update a query (partial update)"""
        query = self.get_object(pk)
        serializer = QueryUpdateSerializer(query, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_query = serializer.save()
            response_serializer = QuerySerializer(updated_query, context={'request': request})
            return Response({
                'message': 'Query updated successfully',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Failed to update query',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Delete query",
        operation_description="Delete a specific query by ID",
        responses={
            200: openapi.Response(description="Query deleted successfully"),
            404: openapi.Response(description="Query not found")
        }
    )
    def delete(self, request, pk):
        """Delete a query and adjust stages of remaining queries"""
        query = self.get_object(pk)
        query_id = query.id
        deleted_stage = query.stage
        session_id = query.session.id
        
        # Delete image file if exists
        if query.image and query.image.name:
            try:
                if query.image.storage.exists(query.image.name):
                    query.image.storage.delete(query.image.name)
            except Exception as e:
                print(f"Error deleting image {query.image.name}: {e}")
        
        # Delete the query
        query.delete()
        
        # Update stages of remaining queries in the same session
        # All queries with stage > deleted_stage should have their stage decreased by 1
        remaining_queries = Query.objects.filter(
            session_id=session_id,
            stage__gt=deleted_stage
        )
        
        for remaining_query in remaining_queries:
            remaining_query.stage = remaining_query.stage - 1
            remaining_query.save()
        
        print(f"Deleted query {query_id} at stage {deleted_stage}, updated {remaining_queries.count()} remaining queries")
        
        return Response({
            'message': f'Query {query_id} deleted successfully and stages adjusted'
        }, status=status.HTTP_200_OK)


class QueryBulkDeleteAPIView(APIView):
    """
    API endpoint for bulk deleting queries
    """
    
    @swagger_auto_schema(
        operation_summary="Bulk delete queries",
        operation_description="Delete multiple queries by providing their IDs",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="Array of query IDs to delete"
                )
            },
            required=['ids']
        ),
        responses={
            200: openapi.Response(description="Queries deleted successfully"),
            400: openapi.Response(description="No query IDs provided")
        }
    )
    def delete(self, request):
        """Bulk delete queries"""
        query_ids = request.data.get('ids', [])
        if not query_ids:
            return Response({
                'message': 'No query IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get queries with images before deleting
        queries_with_images = Query.objects.filter(id__in=query_ids, image__isnull=False)
        
        # Delete image files from storage
        for query in queries_with_images:
            if query.image and query.image.name:
                try:
                    if query.image.storage.exists(query.image.name):
                        query.image.storage.delete(query.image.name)
                except Exception as e:
                    print(f"Error deleting image {query.image.name}: {e}")
        
        # Delete queries from database
        deleted_count, _ = Query.objects.filter(id__in=query_ids).delete()
        return Response({
            'message': f'{deleted_count} queries deleted successfully',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)


class QueryAnswersAPIView(APIView):
    """
    API endpoint for getting answers of a specific query
    """
    
    @swagger_auto_schema(
        operation_summary="Get query answers",
        operation_description="Get all answers for a specific query",
        responses={
            200: openapi.Response(
                description="Answers retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            ),
            404: openapi.Response(description="Query not found")
        }
    )
    def get(self, request, pk):
        """Get all answers for a specific query"""
        query = get_object_or_404(Query, pk=pk)
        answers = query.answers.all()
        serializer = AnswerSerializer(answers, many=True, context={'request': request})
        return Response({
            'message': 'Answers retrieved successfully',
            'data': serializer.data,
            'total': answers.count()
        }, status=status.HTTP_200_OK)


# ===== ANSWER VIEWS =====

class AnswerListCreateAPIView(APIView):
    """
    API endpoint for listing and creating answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="List all answers",
        operation_description="Get a paginated list of all answers with optional filtering",
        manual_parameters=[
            openapi.Parameter('round', openapi.IN_QUERY, description="Filter by round: 'prelims' or 'final'", type=openapi.TYPE_STRING),
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index", type=openapi.TYPE_INTEGER),
            openapi.Parameter('video_name', openapi.IN_QUERY, description="Filter by video name", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Answers retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pages': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            )
        }
    )
    def get(self, request):
        """List all answers with optional filtering"""
        queryset = Answer.objects.all().order_by('-created_at')
        
        # Apply filters
        round_filter = request.query_params.get('round')
        if round_filter:
            queryset = queryset.filter(round=round_filter)
        
        query_index_filter = request.query_params.get('query_index')
        if query_index_filter:
            queryset = queryset.filter(query_index=query_index_filter)
        
        video_name_filter = request.query_params.get('video_name')
        if video_name_filter:
            queryset = queryset.filter(video_name__icontains=video_name_filter)
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page_number = int(request.query_params.get('page', 1))
        
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        
        serializer = AnswerSerializer(page.object_list, many=True, context={'request': request})
        
        return Response({
            'message': 'Answers retrieved successfully',
            'data': serializer.data,
            'total': paginator.count,
            'page': page_number,
            'pages': paginator.num_pages,
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create a new answer",
        operation_description="Create a new answer submission",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index', 'url'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'url': openapi.Schema(type=openapi.TYPE_STRING, description="URL of the frame image"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text (optional)"),
                'query_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Query index (default: 0)"),
                'round': openapi.Schema(type=openapi.TYPE_STRING, description="Round type: 'prelims' or 'final' (default: 'prelims')"),
            }
        ),
        responses={
            201: openapi.Response(
                description="Answer created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data")
        }
    )
    def post(self, request):
        """Create a new answer"""
        serializer = AnswerCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            answer = serializer.save()
            response_serializer = AnswerSerializer(answer, context={'request': request})
            return Response({
                'message': 'Answer created successfully',
                'data': response_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AnswerDetailAPIView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific answer
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Get answer details",
        operation_description="Retrieve details of a specific answer",
        responses={
            200: openapi.Response(
                description="Answer retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            404: openapi.Response(description="Answer not found")
        }
    )
    def get(self, request, answer_id):
        """Get a specific answer"""
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({
                'message': 'Answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AnswerSerializer(answer, context={'request': request})
        return Response({
            'message': 'Answer retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Update answer",
        operation_description="Update a specific answer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'url': openapi.Schema(type=openapi.TYPE_STRING, description="URL of the frame image"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text (optional)"),
                'query_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Query index"),
                'round': openapi.Schema(type=openapi.TYPE_STRING, description="Round type: 'prelims' or 'final'"),
            }
        ),
        responses={
            200: openapi.Response(
                description="Answer updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
            404: openapi.Response(description="Answer not found")
        }
    )
    def put(self, request, answer_id):
        """Update a specific answer"""
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({
                'message': 'Answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AnswerSerializer(answer, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            answer = serializer.save()
            return Response({
                'message': 'Answer updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Delete answer",
        operation_description="Delete a specific answer",
        responses={
            200: openapi.Response(
                description="Answer deleted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            404: openapi.Response(description="Answer not found")
        }
    )
    def delete(self, request, answer_id):
        """Delete a specific answer"""
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({
                'message': 'Answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        answer.delete()
        return Response({
            'message': 'Answer deleted successfully'
        }, status=status.HTTP_200_OK)


class AnswerBulkDeleteAPIView(APIView):
    """
    API endpoint for bulk deleting answers
    """
    
    @swagger_auto_schema(
        operation_summary="Bulk delete answers",
        operation_description="Delete multiple answers by providing their IDs",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="Array of answer IDs to delete"
                )
            },
            required=['ids']
        ),
        responses={
            200: openapi.Response(description="Answers deleted successfully"),
            400: openapi.Response(description="No answer IDs provided")
        }
    )
    def delete(self, request):
        """Bulk delete answers"""
        answer_ids = request.data.get('ids', [])
        if not answer_ids:
            return Response({
                'message': 'No answer IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        deleted_count, _ = Answer.objects.filter(id__in=answer_ids).delete()
        return Response({
            'message': f'{deleted_count} answers deleted successfully',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)


class AnswersByQueryAPIView(APIView):
    """
    API endpoint for getting answers by query ID
    """
    
    @swagger_auto_schema(
        operation_summary="Get answers by query ID",
        operation_description="Get all answers for a specific query by query_id parameter",
        manual_parameters=[
            openapi.Parameter('query_id', openapi.IN_QUERY, description="Query ID", type=openapi.TYPE_INTEGER, required=True),
        ],
        responses={
            200: openapi.Response(
                description="Answers retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'query_info': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            400: openapi.Response(description="query_id parameter is required"),
            404: openapi.Response(description="Query not found")
        }
    )
    def get(self, request):
        """Get all answers for a specific query by query_id parameter"""
        query_id = request.query_params.get('query_id')
        if not query_id:
            return Response({
                'message': 'query_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            query = Query.objects.get(id=query_id)
        except Query.DoesNotExist:
            return Response({
                'message': 'Query not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        answers = Answer.objects.filter(query_id=query_id).order_by('-created_at')
        serializer = AnswerSerializer(answers, many=True, context={'request': request})
        return Response({
            'message': 'Answers retrieved successfully',
            'data': serializer.data,
            'total': answers.count(),
            'query_info': {
                'id': query.id,
                'text': query.text,
                'created_at': query.created_at
            }
        }, status=status.HTTP_200_OK)


class QuerySessionListCreateAPIView(APIView):
    """
    API endpoint for listing and creating query sessions
    """
    
    @swagger_auto_schema(
        operation_summary="List all query sessions",
        operation_description="Get a list of all query sessions ordered by creation date",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Sessions retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pages': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            )
        }
    )
    def get(self, request):
        """Get all query sessions with pagination"""
        queryset = QuerySession.objects.all().order_by('-created_at')
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page_number = int(request.query_params.get('page', 1))
        
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        
        serializer = QuerySessionSerializer(page.object_list, many=True, context={'request': request})
        
        return Response({
            'message': 'Sessions retrieved successfully',
            'data': serializer.data,
            'total': paginator.count,
            'page': page_number,
            'pages': paginator.num_pages
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create a new query session",
        operation_description="Create a new query session",
        responses={
            201: openapi.Response(
                description="Session created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            )
        }
    )
    def post(self, request):
        """Create a new query session"""
        session = QuerySession.objects.create()
        serializer = QuerySessionSerializer(session, context={'request': request})
        
        return Response({
            'message': 'Session created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)


class QuerySessionDetailAPIView(APIView):
    """
    API endpoint for retrieving, updating and deleting a specific query session
    """
    
    @swagger_auto_schema(
        operation_summary="Get a query session",
        operation_description="Retrieve a specific query session by ID",
        responses={
            200: openapi.Response(
                description="Session retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            404: openapi.Response(description="Session not found")
        }
    )
    def get(self, request, session_id):
        """Get a specific query session"""
        try:
            session = QuerySession.objects.get(id=session_id)
        except QuerySession.DoesNotExist:
            return Response({
                'message': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = QuerySessionSerializer(session, context={'request': request})
        return Response({
            'message': 'Session retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Delete a query session",
        operation_description="Delete a specific query session and all associated queries",
        responses={
            200: openapi.Response(description="Session deleted successfully"),
            404: openapi.Response(description="Session not found")
        }
    )
    def delete(self, request, session_id):
        """Delete a query session and all associated queries"""
        try:
            session = QuerySession.objects.get(id=session_id)
        except QuerySession.DoesNotExist:
            return Response({
                'message': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Delete associated images before deleting queries
        queries = session.queries.all()
        for query in queries:
            if query.image:
                query.image.delete(save=False)
        
        session.delete()
        
        return Response({
            'message': 'Session deleted successfully'
        }, status=status.HTTP_200_OK)


class QuerySessionQueriesAPIView(APIView):
    """
    API endpoint for getting queries in a specific session
    """
    
    @swagger_auto_schema(
        operation_summary="Get queries in a session",
        operation_description="Get all queries in a specific session",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Queries retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pages': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'session_info': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            404: openapi.Response(description="Session not found")
        }
    )
    def get(self, request, session_id):
        """Get all queries in a specific session"""
        try:
            session = QuerySession.objects.get(id=session_id)
        except QuerySession.DoesNotExist:
            return Response({
                'message': 'Session not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        queryset = Query.objects.filter(session=session).order_by('-created_at')
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page_number = int(request.query_params.get('page', 1))
        
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        
        serializer = QuerySerializer(page.object_list, many=True, context={'request': request})
        
        return Response({
            'message': 'Queries retrieved successfully',
            'data': serializer.data,
            'total': paginator.count,
            'page': page_number,
            'pages': paginator.num_pages,
            'session_info': {
                'id': session.id,
                'created_at': session.created_at,
                'updated_at': session.updated_at
            }
        }, status=status.HTTP_200_OK)


class TeamAnswerListCreateAPIView(APIView):
    """
    API endpoint for listing and creating team answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="List all team answers",
        operation_description="Get a paginated list of all team answers with optional filtering",
        manual_parameters=[
            openapi.Parameter('round', openapi.IN_QUERY, description="Filter by round: 'prelims' or 'final'", type=openapi.TYPE_STRING),
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index", type=openapi.TYPE_INTEGER),
            openapi.Parameter('video_name', openapi.IN_QUERY, description="Filter by video name", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="Team answers retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pages': openapi.Schema(type=openapi.TYPE_INTEGER),
                    }
                )
            )
        }
    )
    def get(self, request):
        """List all team answers with optional filtering"""
        queryset = TeamAnswer.objects.all().order_by('-created_at')
        
        # Apply filters
        round_filter = request.query_params.get('round')
        if round_filter:
            queryset = queryset.filter(round=round_filter)
        
        query_index_filter = request.query_params.get('query_index')
        if query_index_filter:
            queryset = queryset.filter(query_index=query_index_filter)
        
        video_name_filter = request.query_params.get('video_name')
        if video_name_filter:
            queryset = queryset.filter(video_name__icontains=video_name_filter)
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 10))
        page_number = int(request.query_params.get('page', 1))
        
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        
        serializer = TeamAnswerSerializer(page.object_list, many=True, context={'request': request})
        
        return Response({
            'message': 'Team answers retrieved successfully',
            'data': serializer.data,
            'total': paginator.count,
            'page': page_number,
            'pages': paginator.num_pages,
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create a new team answer",
        operation_description="Create a new team answer submission (temporary answer)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index', 'url'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'url': openapi.Schema(type=openapi.TYPE_STRING, description="URL of the frame image"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text (optional)"),
                'query_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Query index (default: 0)"),
                'round': openapi.Schema(type=openapi.TYPE_STRING, description="Round type: 'prelims' or 'final' (default: 'prelims')"),
            }
        ),
        responses={
            201: openapi.Response(
                description="Team answer created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data or duplicate entry"),
            409: openapi.Response(description="Team answer already exists for this combination")
        }
    )
    def post(self, request):
        """Create a new team answer"""
        serializer = TeamAnswerCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                team_answer = serializer.save()
                response_serializer = TeamAnswerSerializer(team_answer, context={'request': request})
                return Response({
                    'message': 'Team answer created successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                # Handle database unique constraint error
                if 'unique constraint' in str(e).lower() or 'duplicate' in str(e).lower():
                    return Response({
                        'message': 'Team answer already exists for this video, frame, and query index combination',
                        'errors': {'non_field_errors': ['Duplicate entry']}
                    }, status=status.HTTP_409_CONFLICT)
                else:
                    return Response({
                        'message': 'Error creating team answer',
                        'errors': {'non_field_errors': [str(e)]}
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TeamAnswerDetailAPIView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific team answer
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Get team answer details",
        operation_description="Retrieve details of a specific team answer",
        responses={
            200: openapi.Response(
                description="Team answer retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            404: openapi.Response(description="Team answer not found")
        }
    )
    def get(self, request, team_answer_id):
        """Get a specific team answer"""
        try:
            team_answer = TeamAnswer.objects.get(id=team_answer_id)
        except TeamAnswer.DoesNotExist:
            return Response({
                'message': 'Team answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TeamAnswerSerializer(team_answer, context={'request': request})
        return Response({
            'message': 'Team answer retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Update team answer",
        operation_description="Update a specific team answer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'url': openapi.Schema(type=openapi.TYPE_STRING, description="URL of the frame image"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text (optional)"),
                'query_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Query index"),
                'round': openapi.Schema(type=openapi.TYPE_STRING, description="Round type: 'prelims' or 'final'"),
            }
        ),
        responses={
            200: openapi.Response(
                description="Team answer updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_OBJECT),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
            404: openapi.Response(description="Team answer not found"),
            409: openapi.Response(description="Duplicate entry")
        }
    )
    def put(self, request, team_answer_id):
        """Update a specific team answer"""
        try:
            team_answer = TeamAnswer.objects.get(id=team_answer_id)
        except TeamAnswer.DoesNotExist:
            return Response({
                'message': 'Team answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TeamAnswerCreateSerializer(team_answer, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            try:
                team_answer = serializer.save()
                response_serializer = TeamAnswerSerializer(team_answer, context={'request': request})
                return Response({
                    'message': 'Team answer updated successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                # Handle database unique constraint error
                if 'unique constraint' in str(e).lower() or 'duplicate' in str(e).lower():
                    return Response({
                        'message': 'Team answer already exists for this video, frame, and query index combination',
                        'errors': {'non_field_errors': ['Duplicate entry']}
                    }, status=status.HTTP_409_CONFLICT)
                else:
                    return Response({
                        'message': 'Error updating team answer',
                        'errors': {'non_field_errors': [str(e)]}
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Delete team answer",
        operation_description="Delete a specific team answer",
        responses={
            200: openapi.Response(
                description="Team answer deleted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            404: openapi.Response(description="Team answer not found")
        }
    )
    def delete(self, request, team_answer_id):
        """Delete a specific team answer"""
        try:
            team_answer = TeamAnswer.objects.get(id=team_answer_id)
        except TeamAnswer.DoesNotExist:
            return Response({
                'message': 'Team answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        team_answer.delete()
        return Response({
            'message': 'Team answer deleted successfully'
        }, status=status.HTTP_200_OK)


class TeamAnswerBulkDeleteAPIView(APIView):
    """
    API endpoint for bulk deleting team answers with filtering
    """
    
    @swagger_auto_schema(
        operation_summary="Bulk delete team answers",
        operation_description="Delete team answers with optional filtering by round, query_index, and video_name",
        manual_parameters=[
            openapi.Parameter('round', openapi.IN_QUERY, description="Filter by round: 'prelims' or 'final'", type=openapi.TYPE_STRING),
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index", type=openapi.TYPE_INTEGER),
            openapi.Parameter('video_name', openapi.IN_QUERY, description="Filter by video name", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(description="Team answers deleted successfully"),
            404: openapi.Response(description="No team answers found matching the criteria")
        }
    )
    def delete(self, request):
        """Bulk delete team answers with optional filtering"""
        queryset = TeamAnswer.objects.all()
        
        # Apply filters
        round_filter = request.query_params.get('round')
        if round_filter:
            queryset = queryset.filter(round=round_filter)
        
        query_index_filter = request.query_params.get('query_index')
        if query_index_filter:
            queryset = queryset.filter(query_index=query_index_filter)
        
        video_name_filter = request.query_params.get('video_name')
        if video_name_filter:
            queryset = queryset.filter(video_name__icontains=video_name_filter)
        
        # Check if any team answers match the criteria
        count = queryset.count()
        if count == 0:
            return Response({
                'message': 'No team answers found matching the criteria',
                'deleted_count': 0
            }, status=status.HTTP_200_OK)
        
        # Delete the filtered team answers
        deleted_count, _ = queryset.delete()
        
        return Response({
            'message': f'{deleted_count} team answers deleted successfully',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)
