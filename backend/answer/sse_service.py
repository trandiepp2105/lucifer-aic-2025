import json
import redis
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class TeamAnswerSSEService:
    """
    Server-Sent Events service for TeamAnswer real-time updates
    Uses Redis pub/sub for message broadcasting
    """
    
    CHANNEL_NAME = "team_answers_updates"
    
    def __init__(self):
        """Initialize Redis connection"""
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection with detailed error handling"""
        try:
            # Use Redis configuration from Django settings
            redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
            redis_port = int(getattr(settings, 'REDIS_PORT', 6379))
            redis_password = getattr(settings, 'REDIS_PASSWORD', None)
            redis_db = int(getattr(settings, 'REDIS_DB', 0))
            
            logger.info(f"Initializing Redis connection: {redis_host}:{redis_port}, DB: {redis_db}")
            
            # Use password directly from settings
            password = redis_password
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=password,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Redis connection established successfully for SSE service")
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection error: {e}")
            self.redis_client = None
        except redis.TimeoutError as e:
            logger.error(f"❌ Redis timeout error: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"❌ Unexpected Redis error: {e}")
            self.redis_client = None

    def publish_simple_message(self, message_type, data):
        """
        Simple publish method for team answer updates
        
        Args:
            message_type (str): Type of message ('create' or 'delete')
            data: Data to send
        """
        if not self.redis_client:
            logger.warning("Redis not available, skipping SSE publish")
            return

        message = {
            "type": message_type,
            "data": data,
            "timestamp": timezone.now().isoformat()
        }
        
        try:
            self.redis_client.publish(self.CHANNEL_NAME, json.dumps(message))
            logger.info(f"Published team answer {message_type} event")
        except Exception as e:
            logger.error(f"Failed to publish team answer {message_type} event: {e}")

    def ensure_redis_connection(self):
        """Ensure Redis connection is available, retry if needed"""
        if self.redis_client is None:
            logger.warning("Redis client is None, attempting to reconnect...")
            self._initialize_redis()
            return self.redis_client is not None
            
        try:
            # Test existing connection
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}, attempting to reconnect...")
            self._initialize_redis()
            return self.redis_client is not None


# Global instance
team_answer_sse_service = TeamAnswerSSEService()
