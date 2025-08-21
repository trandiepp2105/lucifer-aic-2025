import json
import redis
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class TeamTRAKEAnswerSSEService:
    """
    Server-Sent Events service for TeamTRAKEAnswer real-time updates
    Uses Redis pub/sub for message broadcasting
    """
    
    CHANNEL_NAME = "team_trake_answers_updates"
    
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
            
            logger.info(f"Initializing Redis connection for TeamTRAKE: {redis_host}:{redis_port}, DB: {redis_db}")
            
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
            logger.info("✅ Redis connection established successfully for TeamTRAKE SSE service")
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection error for TeamTRAKE: {e}")
            self.redis_client = None
        except redis.TimeoutError as e:
            logger.error(f"❌ Redis timeout error for TeamTRAKE: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"❌ Unexpected Redis error for TeamTRAKE: {e}")
            self.redis_client = None

    def publish_create_message(self, data):
        """
        Publish create message for TeamTRAKEAnswer updates
        
        Args:
            data: Data to send (list of created items or single item)
        """
        self.publish_simple_message('create', data)

    def publish_bulk_delete_message(self, deleted_count, deleted_ids=None):
        """
        Publish bulk delete message for TeamTRAKEAnswer updates
        
        Args:
            deleted_count (int): Number of items deleted
            deleted_ids (list): List of deleted IDs (optional)
        """
        data = {
            'deleted_count': deleted_count,
            'deleted_ids': deleted_ids or []
        }
        self.publish_simple_message('bulk_delete', data)

    def publish_group_delete_message(self, deleted_count, group, query_index=None):
        """
        Publish group delete message for TeamTRAKEAnswer updates
        
        Args:
            deleted_count (int): Number of items deleted
            group (int): Group that was deleted
            query_index (int): Query index filter (optional)
        """
        data = {
            'deleted_count': deleted_count,
            'group': group,
            'query_index': query_index
        }
        self.publish_simple_message('group_delete', data)

    def publish_simple_message(self, message_type, data):
        """
        Simple publish method for team TRAKE answer updates
        
        Args:
            message_type (str): Type of message ('create', 'bulk_delete', 'group_delete')
            data: Data to send
        """
        if not self.redis_client:
            logger.warning("Redis not available, skipping TeamTRAKE SSE publish")
            return

        message = {
            "type": message_type,
            "data": data,
            "timestamp": timezone.now().isoformat()
        }
        
        try:
            self.redis_client.publish(self.CHANNEL_NAME, json.dumps(message))
            logger.info(f"Published TeamTRAKEAnswer {message_type} event")
        except Exception as e:
            logger.error(f"Failed to publish TeamTRAKEAnswer {message_type} event: {e}")

    def publish_group_update_message(self, updated_count, item_ids, new_group):
        """
        Publish group update message via Redis
        
        Args:
            updated_count (int): Number of items updated
            item_ids (list): List of updated item IDs
            new_group (int): New group number assigned
        """
        try:
            if not self.ensure_redis_connection():
                logger.error("Redis not available for TeamTRAKE group update message")
                return False
            
            message_data = {
                'type': 'group_update',
                'updated_count': updated_count,
                'item_ids': item_ids,
                'new_group': new_group,
                'timestamp': timezone.now().isoformat(),
                'message': f'Updated group for {updated_count} items to group {new_group}'
            }
            
            message_json = json.dumps(message_data)
            self.redis_client.publish(self.CHANNEL_NAME, message_json)
            
            logger.info(f"Published TeamTRAKE group update message: {updated_count} items to group {new_group}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing TeamTRAKE group update message: {e}")
            return False

    def ensure_redis_connection(self):
        """Ensure Redis connection is available, retry if needed"""
        if self.redis_client is None:
            logger.warning("Redis client is None for TeamTRAKE, attempting to reconnect...")
            self._initialize_redis()
            return self.redis_client is not None
            
        try:
            # Test existing connection
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis ping failed for TeamTRAKE: {e}, attempting to reconnect...")
            self._initialize_redis()
            return self.redis_client is not None


# Global instance
team_trake_answer_sse_service = TeamTRAKEAnswerSSEService()
