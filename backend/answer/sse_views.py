import json
import logging
import time
from django.views import View
from django.http import StreamingHttpResponse
from django.utils import timezone
from .sse_service import team_answer_sse_service

logger = logging.getLogger(__name__)


class TeamAnswerSSEView(View):
    """
    Server-Sent Events view for real-time TeamAnswer updates
    Clean implementation using Django View and existing SSE service
    """
    
    def get(self, request):
        """
        Establish SSE connection for real-time team answer updates
        
        Returns:
            StreamingHttpResponse: SSE stream
        """
        return self._create_sse_response()
    
    def _create_sse_response(self):
        """
        Create SSE response with proper headers
        
        Returns:
            StreamingHttpResponse: Configured SSE response
        """
        response = StreamingHttpResponse(
            self._event_stream(),
            content_type='text/event-stream; charset=utf-8'
        )
        
        # Set SSE headers
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response['Access-Control-Allow-Headers'] = 'Cache-Control, Accept'
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        
        return response
    
    def _event_stream(self):
        """
        Generator function for SSE events
        Uses existing SSE service for Redis connection and message handling
        
        Yields:
            str: SSE formatted event data
        """
        pubsub = None
        
        try:
            # Check and ensure Redis connection
            if not team_answer_sse_service.ensure_redis_connection():
                logger.error("Failed to establish Redis connection for SSE")
                yield self._format_sse_message({
                    'type': 'error', 
                    'message': 'Real-time updates unavailable - Redis connection failed'
                })
                return
            
            # Subscribe to Redis channel
            pubsub = team_answer_sse_service.redis_client.pubsub()
            pubsub.subscribe(team_answer_sse_service.CHANNEL_NAME)
            
            logger.info("Client subscribed to team answers SSE")
            
            # Send connection confirmation
            yield self._format_sse_message({
                'type': 'connected',
                'message': 'Connected to team answers real-time updates',
                'timestamp': timezone.now().isoformat()
            })
            
            # Listen for messages with non-blocking approach
            while True:
                try:
                    # Get message with timeout to prevent blocking
                    message = pubsub.get_message(timeout=1.0)
                    
                    if message is not None:
                        if message['type'] == 'message':
                            try:
                                # Forward the message data
                                yield f"data: {message['data']}\n\n"
                            except Exception as e:
                                logger.error(f"Error forwarding SSE message: {e}")
                                # Don't break, continue the loop
                                continue
                        elif message['type'] == 'subscribe':
                            # Ignore subscription confirmation
                            continue
                    else:
                        # No message received, send keep-alive to prevent timeout
                        yield ": keep-alive\n\n"
                        
                except Exception as e:
                    logger.error(f"Error in SSE message loop: {e}")
                    # Don't break on Redis timeout, continue the loop
                    continue
                    
        except Exception as e:
            logger.error(f"SSE Connection Error: {e}")
            yield self._format_sse_message({
                'type': 'error',
                'message': 'Connection error occurred',
                'timestamp': timezone.now().isoformat()
            })
        finally:
            if pubsub:
                try:
                    pubsub.unsubscribe(team_answer_sse_service.CHANNEL_NAME)
                    pubsub.close()
                    logger.info("Client unsubscribed from team answers SSE")
                except Exception as e:
                    logger.warning(f"Error closing pubsub connection: {e}")
    
    def _format_sse_message(self, data):
        """
        Format data as SSE message
        
        Args:
            data (dict): Message data to format
            
        Returns:
            str: Formatted SSE message
        """
        return f"data: {json.dumps(data)}\n\n"
