from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import random

logger = logging.getLogger(__name__)


class SubmitKISAnswerView(APIView):
    """
    API endpoint for submitting KIS answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Submit KIS answer",
        operation_description="Submit a single frame item as KIS answer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
            }
        ),
        responses={
            200: openapi.Response(
                description="KIS answer submitted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, description="correct or incorrect"),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
        }
    )
    def post(self, request):
        """Submit KIS answer"""
        try:
            video_name = request.data.get('video_name')
            frame_index = request.data.get('frame_index')

            # Validate required fields only
            if not video_name:
                return Response({
                    'status': 'error',
                    'message': 'video_name is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if frame_index is None:
                return Response({
                    'status': 'error',
                    'message': 'frame_index is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Submitting KIS answer - Video: {video_name}, Frame: {frame_index}")

            # Mock evaluation logic - randomly return correct/incorrect
            is_correct = random.choice([True, False])
            submission_status = "correct" if is_correct else "incorrect"
            
            return Response({
                'status': submission_status,
                'message': f'KIS answer {submission_status}'
            }, status=status.HTTP_200_OK)

        except Exception as error:
            logger.error(f"Error submitting KIS answer: {error}")
            return Response({
                'message': f'Error submitting KIS answer: {str(error)}',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubmitQAAnswerView(APIView):
    """
    API endpoint for submitting QA answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Submit QA answer",
        operation_description="Submit a single frame item with QA text as QA answer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index', 'qa'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text"),
            }
        ),
        responses={
            200: openapi.Response(
                description="QA answer submitted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, description="correct or incorrect"),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
        }
    )
    def post(self, request):
        """Submit QA answer"""
        try:
            video_name = request.data.get('video_name')
            frame_index = request.data.get('frame_index')
            qa = request.data.get('qa')

            # Validate required fields only
            if not video_name:
                return Response({
                    'status': 'error',
                    'message': 'video_name is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if frame_index is None:
                return Response({
                    'status': 'error',
                    'message': 'frame_index is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not qa:
                return Response({
                    'status': 'error',
                    'message': 'qa is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Submitting QA answer - Video: {video_name}, Frame: {frame_index}, QA: {qa[:50]}...")

            # Mock evaluation logic - randomly return correct/incorrect
            is_correct = random.choice([True, False])
            submission_status = "correct" if is_correct else "incorrect"
            
            return Response({
                'status': submission_status,
                'message': f'QA answer {submission_status}'
            }, status=status.HTTP_200_OK)

        except Exception as error:
            logger.error(f"Error submitting QA answer: {error}")
            return Response({
                'status': 'error',
                'message': f'Error submitting QA answer: {str(error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubmitTRAKEAnswerView(APIView):
    """
    API endpoint for submitting TRAKE answers
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Submit TRAKE answer",
        operation_description="Submit a list of frame items as TRAKE answer",
        request_body=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                required=['video_name', 'frame_index'],
                properties={
                    'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                    'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                    'group': openapi.Schema(type=openapi.TYPE_INTEGER, description="Group number (optional)"),
                }
            ),
            description="List of frame items to submit"
        ),
        responses={
            200: openapi.Response(
                description="TRAKE answer submitted successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, description="correct or incorrect"),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
        }
    )
    def post(self, request):
        """Submit TRAKE answer"""
        try:
            items = request.data

            # Validate required fields
            if not items or not isinstance(items, list):
                return Response({
                    'status': 'error',
                    'message': 'Request body must be a list of frame items'
                }, status=status.HTTP_400_BAD_REQUEST)

            if len(items) == 0:
                return Response({
                    'status': 'error',
                    'message': 'Frame items list cannot be empty'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate each item
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    return Response({
                        'status': 'error',
                        'message': f'Item {i} must be an object'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if not item.get('video_name'):
                    return Response({
                        'status': 'error',
                        'message': f'Item {i} is missing video_name'
                    }, status=status.HTTP_400_BAD_REQUEST)

                if item.get('frame_index') is None:
                    return Response({
                        'status': 'error',
                        'message': f'Item {i} is missing frame_index'
                    }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Submitting TRAKE answer - Items: {len(items)}")

            # Mock evaluation logic - randomly return correct/incorrect
            is_correct = random.choice([True, False])
            submission_status = "correct" if is_correct else "incorrect"
            
            return Response({
                'status': submission_status,
                'message': f'TRAKE answer {submission_status}'
            }, status=status.HTTP_200_OK)

        except Exception as error:
            logger.error(f"Error submitting TRAKE answer: {error}")
            return Response({
                'status': 'error',
                'message': f'Error submitting TRAKE answer: {str(error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
