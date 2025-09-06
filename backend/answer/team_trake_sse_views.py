import json
import logging
import time
import asyncio
from django.views import View
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from asgiref.sync import sync_to_async

from .models import TeamTRAKEAnswer
from .serializers import (
    TeamTRAKEAnswerSerializer, 
    TeamTRAKEAnswerCreateSerializer, 
    TeamTRAKEAnswerBulkCreateSerializer
)
from .team_trake_sse_service import team_trake_answer_sse_service

logger = logging.getLogger(__name__)


class TeamTRAKEAnswerSSEView(View):
    """
    Server-Sent Events view for real-time TeamTRAKEAnswer updates
    Clean implementation using Django View and existing SSE service
    """
    
    async def get(self, request):
        """
        Establish SSE connection for real-time team TRAKE answer updates
        
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
    
    async def _event_stream(self):
        """
        Async generator function for SSE events
        Uses existing SSE service for Redis connection and message handling
        
        Yields:
            str: SSE formatted event data
        """
        pubsub = None
        
        try:
            # Check and ensure Redis connection (make it async)
            redis_connected = await sync_to_async(team_trake_answer_sse_service.ensure_redis_connection)()
            if not redis_connected:
                logger.error("Failed to establish Redis connection for TeamTRAKE SSE")
                yield self._format_sse_message({
                    'type': 'error', 
                    'message': 'Real-time updates unavailable - Redis connection failed'
                })
                return
            
            # Subscribe to Redis channel (make it async)
            pubsub = await sync_to_async(team_trake_answer_sse_service.redis_client.pubsub)()
            await sync_to_async(pubsub.subscribe)(team_trake_answer_sse_service.CHANNEL_NAME)
            
            logger.info("Client subscribed to TeamTRAKE answers SSE")
            
            # Send connection confirmation
            yield self._format_sse_message({
                'type': 'connected',
                'message': 'Connected to TeamTRAKE answers real-time updates',
                'timestamp': timezone.now().isoformat()
            })
            
            # Listen for messages with non-blocking approach
            while True:
                try:
                    # Get message with timeout to prevent blocking (make it async)
                    message = await sync_to_async(pubsub.get_message)(timeout=1.0)
                    
                    if message is not None:
                        if message['type'] == 'message':
                            try:
                                # Forward the message data
                                yield f"data: {message['data']}\n\n"
                            except Exception as e:
                                logger.error(f"Error forwarding TeamTRAKE SSE message: {e}")
                                # Don't break, continue the loop
                                continue
                        elif message['type'] == 'subscribe':
                            # Ignore subscription confirmation
                            continue
                    else:
                        # No message received, send keep-alive to prevent timeout
                        yield ": keep-alive\n\n"
                    
                    # Use async sleep instead of blocking
                    await asyncio.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"Error in TeamTRAKE SSE message loop: {e}")
                    # Don't break on Redis timeout, continue the loop
                    await asyncio.sleep(0.5)
                    continue
                    
        except Exception as e:
            logger.error(f"TeamTRAKE SSE Connection Error: {e}")
            yield self._format_sse_message({
                'type': 'error',
                'message': 'Connection error occurred',
                'timestamp': timezone.now().isoformat()
            })
        finally:
            if pubsub:
                try:
                    await sync_to_async(pubsub.unsubscribe)(team_trake_answer_sse_service.CHANNEL_NAME)
                    await sync_to_async(pubsub.close)()
                    logger.info("Client unsubscribed from TeamTRAKE answers SSE")
                except Exception as e:
                    logger.warning(f"Error closing TeamTRAKE pubsub connection: {e}")
    
    def _format_sse_message(self, data):
        """
        Format data as SSE message
        
        Args:
            data (dict): Message data to format
            
        Returns:
            str: Formatted SSE message
        """
        return f"data: {json.dumps(data)}\n\n"


class TeamTRAKEAnswerListCreateSSEAPIView(APIView):
    """
    SSE-enabled API endpoint for listing and creating TeamTRAKEAnswer
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="List TeamTRAKEAnswer by query_index or all",
        operation_description="Get TeamTRAKEAnswer grouped by group for a specific query_index or all query_indexes if not specified",
        manual_parameters=[
            openapi.Parameter('query_index', openapi.IN_QUERY, description="Filter by query index (optional)", type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={
            200: openapi.Response(
                description="TeamTRAKEAnswer retrieved successfully",
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
        """List TeamTRAKEAnswer grouped by group for specific query_index or all"""
        query_index = request.query_params.get('query_index')
        
        if query_index is not None:
            # Single query_index case (existing behavior)
            try:
                query_index = int(query_index)
            except ValueError:
                return Response({
                    'message': 'query_index must be a valid integer',
                    'data': []
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get all TeamTRAKEAnswer for the query_index
            queryset = TeamTRAKEAnswer.objects.filter(query_index=query_index).order_by('-created_at')
            
            # Group by group field
            grouped_data = {}
            for item in queryset:
                group_key = item.group
                if group_key not in grouped_data:
                    grouped_data[group_key] = []
                grouped_data[group_key].append(TeamTRAKEAnswerSerializer(item).data)
            
            # Sort items within each group by frame_index ascending
            for group_key in grouped_data:
                grouped_data[group_key].sort(key=lambda x: x.get('frame_index', 0))
            
            # Convert to list of dicts with group and items fields, sorted by group
            result = []
            for group in sorted(grouped_data.keys()):
                result.append({'group': group, 'items': grouped_data[group]})
            
            return Response({
                'message': f'TeamTRAKEAnswer for query_index {query_index} retrieved successfully',
                'data': result
            }, status=status.HTTP_200_OK)
        
        else:
            # All query_indexes case (new behavior)
            # Get all TeamTRAKEAnswer and group by query_index
            all_queryset = TeamTRAKEAnswer.objects.all().order_by('query_index', '-created_at')
            
            # Group by query_index first, then by group within each query_index
            query_data = {}
            for item in all_queryset:
                qi = item.query_index
                if qi not in query_data:
                    query_data[qi] = {}
                
                group_key = item.group
                if group_key not in query_data[qi]:
                    query_data[qi][group_key] = []
                query_data[qi][group_key].append(TeamTRAKEAnswerSerializer(item).data)
            
            # Process each query_index
            result = []
            for qi in sorted(query_data.keys()):
                # Sort items within each group by frame_index ascending
                for group_key in query_data[qi]:
                    query_data[qi][group_key].sort(key=lambda x: x.get('frame_index', 0))
                
                # Convert to list of dicts with group and items fields, sorted by group
                groups_data = []
                for group in sorted(query_data[qi].keys()):
                    groups_data.append({'group': group, 'items': query_data[qi][group]})
                
                result.append({
                    'query_index': qi,
                    'data': groups_data
                })
            
            return Response({
                'message': 'All TeamTRAKEAnswer retrieved successfully',
                'data': result
            }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Create multiple TeamTRAKEAnswer with SSE",
        operation_description="Create multiple TeamTRAKEAnswer from a list of items and broadcast via SSE",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'video_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'frame_index': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'url': openapi.Schema(type=openapi.TYPE_STRING),
                            'query_index': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'group': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            },
            required=['items']
        ),
        responses={
            201: openapi.Response(description="TeamTRAKEAnswer created successfully"),
            400: openapi.Response(description="Validation error")
        }
    )
    def post(self, request):
        """Create multiple TeamTRAKEAnswer from list of items with SSE broadcast"""
        logger.info(f"TeamTRAKE POST request data: {request.data}")
        
        serializer = TeamTRAKEAnswerBulkCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"TeamTRAKE validation failed: {serializer.errors}")
            return Response({
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        items_data = serializer.validated_data['items']
        logger.info(f"TeamTRAKE validated items: {items_data}")
        
        # Validate that all items have the same video_name
        if items_data:
            first_video_name = items_data[0].get('video_name')
            logger.info(f"First video name: {first_video_name}")
            for i, item in enumerate(items_data):
                logger.info(f"Item {i}: video_name={item.get('video_name')}")
                if item.get('video_name') != first_video_name:
                    logger.error(f"Video name mismatch at item {i}: {first_video_name} != {item.get('video_name')}")
                    return Response({
                        'message': 'All items must have the same video name',
                        'error': f'Found different video names: {first_video_name} and {item.get("video_name")}'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        created_items = []
        
        try:
            # Determine group for all items - either from first item or auto-generate
            target_group = None
            if items_data and 'group' in items_data[0] and items_data[0]['group'] is not None:
                target_group = items_data[0]['group']
                
                # Validate that new items have same video_name as existing items in the group
                existing_items_in_group = TeamTRAKEAnswer.objects.filter(group=target_group)
                if existing_items_in_group.exists():
                    existing_video_name = existing_items_in_group.first().video_name
                    new_video_name = items_data[0].get('video_name')
                    
                    if existing_video_name != new_video_name:
                        logger.error(f"Video name mismatch for group {target_group}: existing={existing_video_name}, new={new_video_name}")
                        return Response({
                            'message': f'Cannot add items from video "{new_video_name}" to group {target_group}',
                            'error': f'Group {target_group} already contains items from video "{existing_video_name}". All items in a group must be from the same video.'
                        }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Auto-generate group by finding max group + 1
                max_group = TeamTRAKEAnswer.objects.aggregate(
                    max_group=models.Max('group')
                )['max_group']
                target_group = (max_group or 0) + 1
            
            for item_data in items_data:
                # Ensure all items have the same group
                item_data['group'] = target_group
                
                # Check if (video_name, frame_index) already exists in this group
                existing_item = TeamTRAKEAnswer.objects.filter(
                    group=target_group,
                    video_name=item_data['video_name'],
                    frame_index=item_data['frame_index']
                ).first()
                
                if existing_item:
                    logger.info(f"Item already exists in group {target_group}: {item_data['video_name']} frame {item_data['frame_index']}, skipping...")
                    continue
                
                # Create item if it doesn't exist
                team_trake_answer = TeamTRAKEAnswer.objects.create(**item_data)
                created_items.append(team_trake_answer)
            
            # Broadcast create event via SSE if any items were created
            if created_items:
                serialized_items = [TeamTRAKEAnswerSerializer(item).data for item in created_items]
                # Get query_index from first created item (all items should have same query_index)
                query_index = created_items[0].query_index if created_items else None
                team_trake_answer_sse_service.publish_create_message(serialized_items, query_index)
            
            total_submitted = len(items_data)
            total_created = len(created_items)
            total_skipped = total_submitted - total_created
            
            message_parts = []
            if total_created > 0:
                message_parts.append(f"Created {total_created} new items")
            if total_skipped > 0:
                message_parts.append(f"Skipped {total_skipped} existing items")
            
            message = f"Group {target_group}: " + ", ".join(message_parts) if message_parts else f"No new items added to group {target_group}"
            
            return Response({
                'message': message,
                'data': [TeamTRAKEAnswerSerializer(item).data for item in created_items] if created_items else [],
                'group': target_group,
                'stats': {
                    'submitted': total_submitted,
                    'created': total_created,
                    'skipped': total_skipped
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating TeamTRAKEAnswer: {str(e)}")
            return Response({
                'message': 'Error creating TeamTRAKEAnswer',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TeamTRAKEAnswerBulkDeleteSSEAPIView(APIView):
    """
    SSE-enabled API endpoint for bulk deleting TeamTRAKEAnswer
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Bulk delete TeamTRAKEAnswer by IDs with SSE",
        operation_description="Delete multiple TeamTRAKEAnswer by providing a list of IDs and broadcast via SSE",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="List of TeamTRAKEAnswer IDs to delete"
                )
            },
            required=['ids']
        ),
        responses={
            200: openapi.Response(description="TeamTRAKEAnswer deleted successfully"),
            400: openapi.Response(description="Invalid request")
        }
    )
    def delete(self, request):
        """Bulk delete TeamTRAKEAnswer by IDs with SSE broadcast"""
        ids = request.data.get('ids', [])
        
        if not ids:
            return Response({
                'message': 'IDs list is required and cannot be empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(ids, list):
            return Response({
                'message': 'IDs must be provided as a list'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get query_index from items before deleting (for SSE broadcast)
            items_to_delete = TeamTRAKEAnswer.objects.filter(id__in=ids)
            query_index = items_to_delete.first().query_index if items_to_delete.exists() else None
            
            deleted_count, _ = items_to_delete.delete()
            
            # Broadcast delete event via SSE
            team_trake_answer_sse_service.publish_bulk_delete_message(deleted_count, ids, query_index)
            
            return Response({
                'message': f'Successfully deleted {deleted_count} TeamTRAKEAnswer'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting TeamTRAKEAnswer: {str(e)}")
            return Response({
                'message': 'Error deleting TeamTRAKEAnswer',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TeamTRAKEAnswerGroupDeleteSSEAPIView(APIView):
    """
    SSE-enabled API endpoint for deleting all TeamTRAKEAnswer in a specific group
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Delete all TeamTRAKEAnswer in a group with SSE",
        operation_description="Delete all TeamTRAKEAnswer that belong to a specific group and broadcast via SSE",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'group': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Group identifier to delete all items from"
                ),
                'query_index': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Optional: Filter by query_index as well"
                )
            },
            required=['group']
        ),
        responses={
            200: openapi.Response(description="TeamTRAKEAnswer group deleted successfully"),
            400: openapi.Response(description="Invalid request")
        }
    )
    def delete(self, request):
        """Delete all TeamTRAKEAnswer in a specific group with SSE broadcast"""
        group = request.data.get('group')
        query_index = request.data.get('query_index')
        
        if group is None:
            return Response({
                'message': 'Group parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            group = int(group)
        except (ValueError, TypeError):
            return Response({
                'message': 'Group must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Build filter conditions
            filter_conditions = {'group': group}
            if query_index is not None:
                try:
                    query_index = int(query_index)
                    filter_conditions['query_index'] = query_index
                except (ValueError, TypeError):
                    return Response({
                        'message': 'query_index must be a valid integer'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            deleted_count, _ = TeamTRAKEAnswer.objects.filter(**filter_conditions).delete()
            
            # Broadcast group delete event via SSE
            team_trake_answer_sse_service.publish_group_delete_message(deleted_count, group, query_index)
            
            message = f'Successfully deleted {deleted_count} TeamTRAKEAnswer from group {group}'
            if query_index is not None:
                message += f' with query_index {query_index}'
            
            return Response({
                'message': message
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting TeamTRAKEAnswer group: {str(e)}")
            return Response({
                'message': 'Error deleting TeamTRAKEAnswer group',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TeamTRAKEAnswerUpdateGroupAPIView(APIView):
    """
    API endpoint for updating group assignments for multiple TeamTRAKEAnswer items
    """
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="Update group for multiple TeamTRAKEAnswer items",
        operation_description="Update the group field for multiple TeamTRAKEAnswer items",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'item_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="List of TeamTRAKEAnswer IDs to update"
                ),
                'new_group': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="New group number to assign"
                )
            },
            required=['item_ids', 'new_group']
        ),
        responses={
            200: openapi.Response(description="Group updated successfully"),
            400: openapi.Response(description="Invalid request")
        }
    )
    def patch(self, request):
        """Update group for multiple TeamTRAKEAnswer items"""
        item_ids = request.data.get('item_ids', [])
        new_group = request.data.get('new_group')
        
        if not item_ids:
            return Response({
                'message': 'item_ids list is required and cannot be empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(item_ids, list):
            return Response({
                'message': 'item_ids must be provided as a list'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_group is None:
            return Response({
                'message': 'new_group is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_group = int(new_group)
        except (ValueError, TypeError):
            return Response({
                'message': 'new_group must be a valid integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get query_index from items before updating (for SSE broadcast)
            items_to_update = TeamTRAKEAnswer.objects.filter(id__in=item_ids)
            query_index = items_to_update.first().query_index if items_to_update.exists() else None
            
            updated_count = items_to_update.update(group=new_group)
            
            if updated_count == 0:
                return Response({
                    'message': 'No items were updated. Please check the provided IDs.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Broadcast update event via SSE
            team_trake_answer_sse_service.publish_group_update_message(updated_count, item_ids, new_group, query_index)
            
            return Response({
                'message': f'Successfully updated group for {updated_count} TeamTRAKEAnswer items',
                'updated_count': updated_count,
                'new_group': new_group
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error updating TeamTRAKEAnswer group: {str(e)}")
            return Response({
                'message': 'Error updating TeamTRAKEAnswer group',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
