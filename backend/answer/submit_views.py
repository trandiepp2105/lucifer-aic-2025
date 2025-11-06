from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import requests
import os
from .models import DresSession
from types import SimpleNamespace
logger = logging.getLogger(__name__)


class SubmitKISAnswerView(APIView):
    """
    API endpoint for submitting KIS answers to DRES server
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Submit KIS answer to DRES",
        operation_description="Submit a single frame item as KIS answer with temporal segment to DRES server",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index', 'fps'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'fps': openapi.Schema(type=openapi.TYPE_NUMBER, description="Frames per second of the video"),
            }
        ),
        responses={
            200: openapi.Response(
                description="KIS answer submitted successfully to DRES",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, description="DRES verdict status"),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
            401: openapi.Response(description="No DRES session found"),
            502: openapi.Response(description="DRES server error"),
        }
    )
    def post(self, request):
        """Submit KIS answer to DRES server"""
        try:
            video_name = request.data.get('video_name')
            frame_index = request.data.get('frame_index')
            fps = request.data.get('fps')

            # Validate required fields
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

            if not fps:
                return Response({
                    'status': 'error',
                    'message': 'fps is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # use dres session and evaluation id from request if provided
            dres_session = {
                'session_id': request.data.get('dres_session', None),
                'evaluation_id': request.data.get('evaluation_id', None)
            }
            dres_session = SimpleNamespace(**dres_session)


            # Get latest DRES session
            # try:
            #     dres_session = DresSession.objects.order_by('-created_at').first()
            #     if not dres_session:
            #         return Response({
            #             'status': 'error',
            #             'message': 'No DRES session found. Please login to DRES first.'
            #         }, status=status.HTTP_401_UNAUTHORIZED)

            #     if not dres_session.evaluation_id:
            #         return Response({
            #             'status': 'error',
            #             'message': 'No evaluation ID configured. Please set evaluation ID first.'
            #         }, status=status.HTTP_401_UNAUTHORIZED)

            # except Exception as e:
            #     logger.error(f"Error retrieving DRES session: {e}")
            #     return Response({
            #         'status': 'error',
            #         'message': 'Error retrieving DRES session'
            #     }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Calculate time from frame_index and fps (in milliseconds)
            time_in_seconds = frame_index / fps
            time_in_milliseconds = int(time_in_seconds * 1000)

            # Build DRES payload for KIS (temporal segment)
            dres_payload = {
                "answerSets": [
                    {
                        "answers": [
                            {
                                "mediaItemName": video_name,
                                "start": time_in_milliseconds,
                                "end": time_in_milliseconds
                            }
                        ]
                    }
                ]
            }

            logger.info(f"Submitting KIS answer to DRES - Video: {video_name}, Frame: {frame_index}, Time: {time_in_milliseconds}ms")

            # Get DRES submit endpoint from environment
            dres_submit_base_url = os.getenv('DRES_SUBMIT_ENDPOINT', "http://127.0.0.1:8080/api/v2/submit")
            dres_submit_url = f"{dres_submit_base_url}/{dres_session.evaluation_id}"


            # Submit to DRES server
            try:
                response = requests.post(
                    dres_submit_url,
                    json=dres_payload,
                    params={'session': dres_session.session_id},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if response.status_code in [200, 202]:
                    response_data = response.json()
                    # Forward DRES response directly to client with DRES status code
                    return Response(response_data, status=response.status_code)
                else:
                    logger.error(f"DRES submission failed: {response.status_code} - {response.text}")
                    return Response({
                        'status': 'error',
                        'message': f'DRES server error: {response.text}'
                    }, status=status.HTTP_502_BAD_GATEWAY)

            except requests.exceptions.ConnectionError:
                logger.error("Failed to connect to DRES server")
                return Response({
                    'status': 'error',
                    'message': 'Unable to connect to DRES server'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except requests.exceptions.Timeout:
                logger.error("DRES server request timed out")
                return Response({
                    'status': 'error',
                    'message': 'DRES server request timed out'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)

        except Exception as error:
            logger.error(f"Error submitting KIS answer: {error}")
            return Response({
                'status': 'error',
                'message': f'Error submitting KIS answer: {str(error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubmitQAAnswerView(APIView):
    """
    API endpoint for submitting QA answers to DRES server
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Submit QA answer to DRES",
        operation_description="Submit a single frame item with QA text as QA answer to DRES server",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['video_name', 'frame_index', 'qa', 'fps'],
            properties={
                'video_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the video"),
                'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER, description="Frame index in the video"),
                'qa': openapi.Schema(type=openapi.TYPE_STRING, description="Question and answer text"),
                'fps': openapi.Schema(type=openapi.TYPE_NUMBER, description="Frames per second of the video"),
            }
        ),
        responses={
            200: openapi.Response(
                description="QA answer submitted successfully to DRES",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, description="DRES verdict status"),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
            401: openapi.Response(description="No DRES session found"),
            502: openapi.Response(description="DRES server error"),
        }
    )
    def post(self, request):
        """Submit QA answer to DRES server"""
        try:
            video_name = request.data.get('video_name')
            frame_index = request.data.get('frame_index')
            qa = request.data.get('qa')
            fps = request.data.get('fps')

            # Validate required fields
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

            if not fps:
                return Response({
                    'status': 'error',
                    'message': 'fps is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # use dres session and evaluation id from request if provided
            dres_session = {
                'session_id': request.data.get('dres_session', None),
                'evaluation_id': request.data.get('evaluation_id', None)
            }
            dres_session = SimpleNamespace(**dres_session)
            # # Get latest DRES session
            # try:
            #     dres_session = DresSession.objects.order_by('-created_at').first()
            #     if not dres_session:
            #         return Response({
            #             'status': 'error',
            #             'message': 'No DRES session found. Please login to DRES first.'
            #         }, status=status.HTTP_401_UNAUTHORIZED)

            #     if not dres_session.evaluation_id:
            #         return Response({
            #             'status': 'error',
            #             'message': 'No evaluation ID configured. Please set evaluation ID first.'
            #         }, status=status.HTTP_401_UNAUTHORIZED)

            # except Exception as e:
            #     logger.error(f"Error retrieving DRES session: {e}")
            #     return Response({
            #         'status': 'error',
            #         'message': 'Error retrieving DRES session'
            #     }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Calculate time from frame_index and fps (in milliseconds)
            time_in_seconds = frame_index / fps
            time_in_milliseconds = int(time_in_seconds * 1000)

            # Build DRES payload for QA (text-based with metadata)
            # Format: QA-{answer}-{video_name}-{timestamp}
            text_answer = f"QA-{qa}-{video_name}-{time_in_milliseconds}"
            dres_payload = {
                "answerSets": [
                    {
                        "answers": [
                            {
                                "text": text_answer
                            }
                        ]
                    }
                ]
            }

            logger.info(f"Submitting QA answer to DRES - Video: {video_name}, Frame: {frame_index}, QA: {qa[:50]}..., Time: {time_in_milliseconds}ms")

            # Get DRES submit endpoint from environment
            dres_submit_base_url = os.getenv('DRES_SUBMIT_ENDPOINT', "http://127.0.0.1:8080/api/v2/submit")
            dres_submit_url = f"{dres_submit_base_url}/{dres_session.evaluation_id}"

            # Submit to DRES server
            try:
                response = requests.post(
                    dres_submit_url,
                    json=dres_payload,
                    params={'session': dres_session.session_id},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if response.status_code in [200, 202]:
                    response_data = response.json()
                    # Forward DRES response directly to client with DRES status code
                    return Response(response_data, status=response.status_code)
                else:
                    logger.error(f"DRES QA submission failed: {response.status_code} - {response.text}")
                    return Response({
                        'status': 'error',
                        'message': f'DRES server error: {response.text}'
                    }, status=status.HTTP_502_BAD_GATEWAY)

            except requests.exceptions.ConnectionError:
                logger.error("Failed to connect to DRES server for QA submission")
                return Response({
                    'status': 'error',
                    'message': 'Unable to connect to DRES server'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except requests.exceptions.Timeout:
                logger.error("DRES server QA request timed out")
                return Response({
                    'status': 'error',
                    'message': 'DRES server request timed out'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)

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
            data = request.data
            print("Received TRAKE data:", data)
            
            # Handle both old format (array) and new format (object with frame_items)
            if isinstance(data, dict):
                items = data.get('frame_items', [])
                dres_session = data.get('dres_session')
                evaluation_id = data.get('evaluation_id')
            else:
                items = data
                dres_session = None
                evaluation_id = None
            
            # Validate required fields
            if not items or not isinstance(items, list):
                return Response({
                    'status': 'error',
                    'message': 'Frame items must be a list'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check minimum 4 items required for TRAKE
            if len(items) < 4:
                return Response({
                    'status': 'error',
                    'message': f'TRAKE requires at least 4 items, but only {len(items)} provided'
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

            # Format target for TRAKE submission: TR-{video_name}-frame1,frame2,frame3,frame4
            # Extract video_name from first item (all should be same video)
            video_name = items[0]['video_name']
            
            # Extract frame indices directly (no conversion to milliseconds)
            frame_ids = []
            for item in items:
                frame_index = item['frame_index']
                frame_ids.append(frame_index)
            
            # Sort frame IDs in ascending order
            frame_ids.sort()
            
            # Format: TR-{video_name}-frame1,frame2,frame3,frame4
            target = f"TR-{video_name}-" + ",".join(str(fid) for fid in frame_ids)
            
            logger.info(f"Formatted TRAKE target: {target}")
            logger.info(f"DRES Session: {dres_session}")
            logger.info(f"Evaluation ID: {evaluation_id}")
            
            # Build DRES payload for TRAKE text submission
            dres_payload = {
                "answerSets": [
                    {
                        "answers": [
                            {
                                "text": target
                            }
                        ]
                    }
                ]
            }
            
            # Get DRES submit endpoint from environment
            dres_submit_base_url = os.getenv('DRES_SUBMIT_ENDPOINT', "http://127.0.0.1:8080/api/v2/submit")
            dres_submit_url = f"{dres_submit_base_url}/{evaluation_id}"
            
            logger.info(f"Submitting TRAKE answer to DRES: {dres_submit_url}")
            
            # Submit to DRES server
            try:
                response = requests.post(
                    dres_submit_url,
                    json=dres_payload,
                    params={'session': dres_session},
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code in [200, 202]:
                    response_data = response.json()
                    logger.info(f"DRES TRAKE submission successful: {response_data}")
                    # Forward DRES response directly to client with DRES status code
                    return Response(response_data, status=response.status_code)
                else:
                    logger.error(f"DRES TRAKE submission failed: {response.status_code} - {response.text}")
                    return Response({
                        'status': 'error',
                        'message': f'DRES server error: {response.text}'
                    }, status=status.HTTP_502_BAD_GATEWAY)
                    
            except requests.exceptions.ConnectionError:
                logger.error("Failed to connect to DRES server for TRAKE submission")
                return Response({
                    'status': 'error',
                    'message': 'Unable to connect to DRES server'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except requests.exceptions.Timeout:
                logger.error("DRES server TRAKE request timed out")
                return Response({
                    'status': 'error',
                    'message': 'DRES server request timed out'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)

        except Exception as error:
            logger.error(f"Error submitting TRAKE answer: {error}")
            return Response({
                'status': 'error',
                'message': f'Error submitting TRAKE answer: {str(error)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
