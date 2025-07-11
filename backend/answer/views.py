from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Answer, TeamAnswer
from .serializers import (
    AnswerSerializer, AnswerCreateSerializer,
    TeamAnswerSerializer, TeamAnswerCreateSerializer
)

class AnswerListCreateAPIView(APIView):
    """
    API endpoint for listing and creating answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="List all answers",
        operation_description="Get all answers with optional filtering",
        manual_parameters=[
            openapi.Parameter('round', openapi.IN_QUERY, description="Filter by round: 'prelims' or 'final'", type=openapi.TYPE_STRING),
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index", type=openapi.TYPE_INTEGER),
            openapi.Parameter('video_name', openapi.IN_QUERY, description="Filter by video name", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Answers retrieved successfully",
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
        
        serializer = AnswerSerializer(queryset, many=True, context={'request': request})
        
        return Response({
            'message': 'Answers retrieved successfully',
            'data': serializer.data,
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


class TeamAnswerListCreateAPIView(APIView):
    """
    API endpoint for listing and creating team answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="List all team answers",
        operation_description="Get all team answers with optional filtering",
        manual_parameters=[
            openapi.Parameter('round', openapi.IN_QUERY, description="Filter by round: 'prelims' or 'final'", type=openapi.TYPE_STRING),
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index", type=openapi.TYPE_INTEGER),
            openapi.Parameter('video_name', openapi.IN_QUERY, description="Filter by video name", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Team answers retrieved successfully",
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
        
        serializer = TeamAnswerSerializer(queryset, many=True, context={'request': request})
        
        return Response({
            'message': 'Team answers retrieved successfully',
            'data': serializer.data,
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
