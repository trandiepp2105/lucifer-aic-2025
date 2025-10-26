import os
import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import DresSession
import logging

logger = logging.getLogger(__name__)

class DresLoginView(APIView):
    """
    DRES Login proxy view that forwards authentication requests to DRES server
    """
    
    def post(self, request):
        """
        Forward login request to DRES server
        
        Expected request body:
        {
            "username": "user_name",
            "password": "user_password"
        }
        
        Returns our DresSession data:
        {
            "id": 1,
            "username": "trandiep", 
            "role": "PARTICIPANT",
            "session_id": "AV1BYfEhFVloKtpsH4PqXbrvHjIujBcu",
            "created_at": "2025-09-23T10:30:00Z"
        }
        """
        try:
            # Get DRES login endpoint from environment variables
            dres_login_endpoint = os.getenv('DRES_LOGIN_ENDPOINT')
            
            if not dres_login_endpoint:
                logger.error("DRES_LOGIN_ENDPOINT environment variable not set")
                return Response({
                    'error': 'DRES login endpoint not configured'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Validate request data
            username = request.data.get('username')
            password = request.data.get('password')
            
            if not username or not password:
                return Response({
                    'error': 'Username and password are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Prepare payload for DRES server
            login_payload = {
                'username': username,
                'password': password
            }
            
            # Forward request to DRES server
            logger.info(f"Forwarding login request to DRES: {dres_login_endpoint}")
            
            try:
                dres_response = requests.post(
                    dres_login_endpoint,
                    json=login_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30  # 30 second timeout
                )
                
                # Check if DRES request was successful
                if dres_response.status_code == 200:
                    dres_data = dres_response.json()
                    
                    # Save session information to database
                    try:
                        # Delete all existing DRES sessions to keep only one active session
                        deleted_count = DresSession.objects.all().delete()[0]

                        # Create new session record
                        dres_session = DresSession.objects.create(
                            username=username,
                            role=dres_data.get('role', 'PARTICIPANT'),
                            session_id=dres_data.get('sessionId', '')
                        )
                        
                        # Get evaluation list and find active evaluation
                        active_evaluation_id = None
                        try:
                            # Get DRES evaluation list endpoint (using client API)
                            dres_base_url = os.getenv('DRES_BASE_URL', dres_login_endpoint.rsplit('/login', 1)[0])
                            evaluation_list_endpoint = f"{dres_base_url}/api/v2/client/evaluation/list"
                            

                            # Make request with session as query parameter
                            params = {'session': dres_session.session_id}
                            eval_response = requests.get(
                                evaluation_list_endpoint,
                                params=params,
                                headers={'Content-Type': 'application/json'},
                                timeout=10
                            )
 
                            if eval_response.status_code == 200:
                                # Log raw response for debugging
                                response_text = eval_response.text
    
                                try:
                                    evaluations = eval_response.json()
                                    
                                    # Find the first ACTIVE evaluation
                                    for evaluation in evaluations:
                                        if evaluation.get('status') == 'ACTIVE':
                                            active_evaluation_id = evaluation.get('id')
                                            print(f"Found ACTIVE evaluation: {active_evaluation_id}")
                                            break
                                    
                                    if not active_evaluation_id:
                                        print("WARNING: No ACTIVE evaluation found in the list")
                                        
                                except json.JSONDecodeError as json_error:
                                    print(f"ERROR: Failed to parse evaluation list JSON: {str(json_error)}")
                                    print(f"Response content: {response_text}")
                            else:
                                print(f"WARNING: Failed to fetch evaluation list: {eval_response.status_code}")
                                print(f"Response body: {eval_response.text}")
                                
                        except requests.exceptions.RequestException as req_error:
                            print(f"ERROR: Request error fetching evaluation list: {str(req_error)}")
                        except Exception as eval_error:
                            print(f"ERROR: Unexpected error fetching evaluation list: {str(eval_error)}")
                            # Continue without evaluation_id if this fails
                        
                        # Update session with active evaluation_id if found
                        if active_evaluation_id:
                            dres_session.evaluation_id = active_evaluation_id
                            dres_session.save()
                        
                        # Return our DresSession data instead of DRES server data
                        return Response({
                            'id': dres_session.id,
                            'username': dres_session.username,
                            'role': dres_session.role,
                            'session_id': dres_session.session_id,
                            'evaluation_id': dres_session.evaluation_id,
                            'created_at': dres_session.created_at.isoformat()
                        }, status=status.HTTP_200_OK)

                    except Exception as db_error:
                        print(f"Failed to save DRES session to database: {str(db_error)}")
                        # If DB save fails, return error instead of continuing
                        return Response({
                            'error': 'Failed to save session information'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                elif dres_response.status_code == 401:
                    logger.warning(f"DRES login failed - invalid credentials for user: {username}")
                    return Response({
                        'error': 'Invalid username or password'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                    
                else:
                    logger.error(f"DRES server error: {dres_response.status_code} - {dres_response.text}")
                    return Response({
                        'error': 'DRES server error',
                        'details': dres_response.text if dres_response.text else 'Unknown error'
                    }, status=status.HTTP_502_BAD_GATEWAY)
                    
            except requests.exceptions.ConnectionError:
                logger.error(f"Failed to connect to DRES server: {dres_login_endpoint}")
                return Response({
                    'error': 'Unable to connect to DRES server'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
            except requests.exceptions.Timeout:
                logger.error("DRES server request timed out")
                return Response({
                    'error': 'DRES server request timed out'
                }, status=status.HTTP_504_GATEWAY_TIMEOUT)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request to DRES server failed: {str(e)}")
                return Response({
                    'error': 'Failed to communicate with DRES server'
                }, status=status.HTTP_502_BAD_GATEWAY)
                
        except Exception as e:
            logger.error(f"Unexpected error in DRES login: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DresSessionView(APIView):
    """
    DRES Session view to get the latest session information
    """
    
    def get(self, request):
        """
        Get the latest DRES session
        
        Returns:
        {
            "id": 1,
            "username": "trandiep", 
            "role": "PARTICIPANT",
            "session_id": "AV1BYfEhFVloKtpsH4PqXbrvHjIujBcu",
            "evaluation_id": "eval_123",
            "created_at": "2025-09-23T10:30:00Z"
        }
        
        Or null if no session exists
        """
        try:
            # Get the latest DRES session (most recent by created_at)
            latest_session = DresSession.objects.order_by('-created_at').first()
            
            if latest_session:
                return Response({
                    'id': latest_session.id,
                    'username': latest_session.username,
                    'role': latest_session.role,
                    'session_id': latest_session.session_id,
                    'evaluation_id': latest_session.evaluation_id,
                    'created_at': latest_session.created_at.isoformat()
                }, status=status.HTTP_200_OK)
            else:
                # No session found
                return Response({
                    'session': None,
                    'message': 'No DRES session found'
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error retrieving DRES session: {str(e)}")
            return Response({
                'error': 'Failed to retrieve DRES session'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """
        Update the evaluation_id of the latest DRES session
        
        Expected request body:
        {
            "evaluation_id": "eval_123"
        }
        
        Returns updated session data:
        {
            "id": 1,
            "username": "trandiep", 
            "role": "PARTICIPANT",
            "session_id": "AV1BYfEhFVloKtpsH4PqXbrvHjIujBcu",
            "evaluation_id": "eval_123",
            "created_at": "2025-09-23T10:30:00Z"
        }
        """
        try:
            # Get the latest DRES session (most recent by created_at)
            latest_session = DresSession.objects.order_by('-created_at').first()
            
            if not latest_session:
                return Response({
                    'error': 'No DRES session found to update'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get evaluation_id from request
            evaluation_id = request.data.get('evaluation_id')
            
            if evaluation_id is None:
                return Response({
                    'error': 'evaluation_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update the evaluation_id (can be empty string or null)
            latest_session.evaluation_id = evaluation_id if evaluation_id.strip() else None
            latest_session.save()
            
            logger.info(f"Updated DRES session {latest_session.id} evaluation_id to: {latest_session.evaluation_id}")
            
            return Response({
                'id': latest_session.id,
                'username': latest_session.username,
                'role': latest_session.role,
                'session_id': latest_session.session_id,
                'evaluation_id': latest_session.evaluation_id,
                'created_at': latest_session.created_at.isoformat()
            }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Error updating DRES session evaluation_id: {str(e)}")
            return Response({
                'error': 'Failed to update DRES session'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
