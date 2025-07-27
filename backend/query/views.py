from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import sys
import os
from pathlib import Path
import time
import logging
import requests
from io import BytesIO

# Add search module to path
search_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'search')
if search_path not in sys.path:
    sys.path.append(search_path)

# Import Meilisearch service
from search.meili_search_service import meili_search_service as search_service
SEARCH_ENGINE = "Meilisearch"

from .models import Query, QuerySession
from .serializers import (
    QuerySerializer, QueryCreateSerializer, 
    QueryUpdateSerializer, QuerySessionSerializer
)

class QueryListCreateAPIView(APIView):
    """
    API endpoint for listing and creating queries
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_summary="List all queries",
        operation_description="Get all queries with optional filtering",
        manual_parameters=[
            openapi.Parameter('session', openapi.IN_QUERY, description="Filter by session ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('viewmode', openapi.IN_QUERY, description="View mode for frames: 'gallery' (flat list) or 'samevideo' (grouped by video)", type=openapi.TYPE_STRING),
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
                    }
                )
            )
        }
    )
    def get(self, request):
        """Get all queries with filtering"""
        queryset = Query.objects.all()
        search_url = "https://66fd452b548e.ngrok-free.app/search/"
        # Filter by session
        session_id = request.query_params.get('session')
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        # Get k parameter and convert to int
        k_param = request.query_params.get('k', '50')
        try:
            k = int(k_param)
        except (ValueError, TypeError):
            k = 50  # Default value if conversion fails
            
        queryset = queryset.order_by('-created_at')
        
        serializer = QuerySerializer(queryset, many=True, context={'request': request})
        
        # Search frames for the latest query if it exists
        frames = []
        if queryset:
            # Get the most recent query
            latest_query = queryset[0]  # Already ordered by -created_at
            
            # Perform OCR search on the latest query if it has OCR data
            if latest_query.ocr and latest_query.ocr.strip() and latest_query.ocr.lower() != 'null':
                print(f"Performing OCR search for query {latest_query.id} with text: {latest_query.ocr[:50]}")
                total_start = time.time()
                
                ocr_results = self._search_ocr(ocr_text=latest_query.ocr, k=k)
                raw_frames = self.adjust_response(request, ocr_results)
                
                # Process frames based on viewmode
                viewmode = request.query_params.get('viewmode', 'gallery')
                print(f"View mode: {viewmode}")
                frames = self._process_frames_by_viewmode(raw_frames, viewmode)

                total_end = time.time()
                total_duration = total_end - total_start
                
                print(f"Total OCR process time: {total_duration:.3f} seconds")
                
            elif latest_query.text and latest_query.text.strip() and latest_query.text.lower() != 'null':
                total_start = time.time()
                
                # Perform text search via external API
                text_results = self._search_text(search_url=search_url,text=latest_query.text, k=k)
                raw_frames = self.adjust_faiss_response(request, text_results)
                
                # Process frames based on viewmode
                viewmode = request.query_params.get('viewmode', 'gallery')
                print(f"View mode: {viewmode}")
                frames = self._process_frames_by_viewmode(raw_frames, viewmode)

                total_end = time.time()
                total_duration = total_end - total_start
                
                print(f"Total text search process time: {total_duration:.3f} seconds")
                
            elif latest_query.image:
                total_start = time.time()
                
                # Perform image search via external API
                image_results = self._search_image(search_url=search_url,image=latest_query.image, k=k)
                raw_frames = self.adjust_faiss_response(request, image_results)
                
                # Process frames based on viewmode
                viewmode = request.query_params.get('viewmode', 'gallery')
                print(f"View mode: {viewmode}")
                frames = self._process_frames_by_viewmode(raw_frames, viewmode)

                total_end = time.time()
                total_duration = total_end - total_start
                
                print(f"Total image search process time: {total_duration:.3f} seconds")
                
                print(f"Total text search process time: {total_duration:.3f} seconds")
        
        return Response({
            'message': 'Queries retrieved successfully',
            'data': serializer.data,
            'frames': frames,  # Add frames to response
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
    
    def _search_ocr(self, ocr_text: str, k: int = 50) -> list:
        """
        Perform OCR search using sync method
        
        Args:
            ocr_text: OCR text to search for
            k: Number of results to return
            
        Returns:
            List of search results or empty list if error
        """
        try:
            # Sử dụng sync method 
            results = search_service.search_ocr(ocr_text, size=k)

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

    def adjust_faiss_response(self, request, results: list) -> list:
        """
        Adjust FAISS search results to create frames array with full URLs
        
        Args:
            request: Django request object
            results: List of FAISS search results, each containing [path, score]
                    Format: [["L06_V020/11116.jpg", 0.286108285188675], ...]
            
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
            # FAISS results format: [path, score]
            if len(result) >= 2:
                path = result[0]  # e.g., "L06_V020/11116.jpg"
                score = result[1]
                
                # Parse video_name and frame_index from path
                # Path format: {video_name}/{frame_index}.jpg
                if '/' in path:
                    video_name, filename = path.rsplit('/', 1)
                    frame_index = filename.replace('.jpg', '')
                    
                    # Build frame URL: http://{SERVER_IP}/media/frames/{video_name}/{frame_index}.jpg
                    frame_url = f"{base_url}/media/frames/{video_name}/{frame_index}.jpg"
                    
                    frame_data = {
                        'url': frame_url,
                        'video_name': video_name,
                        'frame_index': frame_index,
                        'score': score
                    }
                    frames.append(frame_data)
        
        return frames
    
    def _search_text(self, search_url: str, text: str, k=10) -> list:
        """
        Perform text search using external search API
        
        Args:
            text: Text query to search for
            k: Number of results to return
            
        Returns:
            List of search results in FAISS format or empty list if error
        """
        try:
            params = {'text': text, 'k': k}
            
            response = requests.get(search_url, params=params, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    results = response_data.get('results', [])
                    print(f"Text search returned {len(results)} results")
                    return results
            
            print(f"Text search API error: {response.status_code} - {response.text}")
            return []
                
        except Exception as e:
            print(f"Text search error: {e}")
            return []

    def _search_image(self, search_url: str, image, k=10) -> list:
        """
        Perform image search using external search API
        
        Args:
            image: Image file from query (Django ImageFieldFile)
            k: Number of results to return
            
        Returns:
            List of search results in FAISS format or empty list if error
        """
        try:
            
            # Open the image file and get its content
            with image.open('rb') as img_file:
                image_content = img_file.read()
            
            # Determine content type from file extension
            import mimetypes
            content_type = mimetypes.guess_type(image.name)[0] or 'image/jpeg'
            
            files = {'image': (image.name, image_content, content_type)}
            data = {'k': k}
            
            response = requests.post(search_url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    results = response_data.get('results', [])
                    print(f"Image search returned {len(results)} results")
                    return results
            
            print(f"Image search API error: {response.status_code} - {response.text}")
            return []
                
        except Exception as e:
            print(f"Image search error: {e}")
            return []

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


class QuerySessionListCreateAPIView(APIView):
    """
    API endpoint for listing and creating query sessions
    """
    
    @swagger_auto_schema(
        operation_summary="List all query sessions",
        operation_description="Get all query sessions ordered by creation date",
        responses={
            200: openapi.Response(
                description="Sessions retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    }
                )
            )
        }
    )
    def get(self, request):
        """Get all query sessions"""
        queryset = QuerySession.objects.all().order_by('-created_at')
        
        serializer = QuerySessionSerializer(queryset, many=True, context={'request': request})
        
        return Response({
            'message': 'Sessions retrieved successfully',
            'data': serializer.data,
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
                query.delete_image_file()
        
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
        responses={
            200: openapi.Response(
                description="Queries retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
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
        
        serializer = QuerySerializer(queryset, many=True, context={'request': request})
        
        return Response({
            'message': 'Queries retrieved successfully',
            'data': serializer.data,
            'session_info': {
                'id': session.id,
                'created_at': session.created_at,
                'updated_at': session.updated_at
            }
        }, status=status.HTTP_200_OK)
