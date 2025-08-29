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
import json
from typing import List, Tuple
import urllib3

# Disable SSL warnings for ngrok URLs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# # Add search module to path
# search_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'search')
# if search_path not in sys.path:
#     sys.path.append(search_path)

# # Import Meilisearch service
# from search.meili_search_service import meili_search_service as search_service
# SEARCH_ENGINE = "Meilisearch"

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

    def _create_request_session(self, url: str) -> requests.Session:
        """
        Create a requests session with appropriate configuration for the URL
        
        Args:
            url: The URL to make requests to
            
        Returns:
            Configured requests session
        """
        session = requests.Session()
        
        # Special configuration for ngrok URLs
        if 'ngrok' in url.lower():
            # Disable SSL verification for ngrok URLs to avoid SSL errors
            session.verify = False
            # Add headers to bypass ngrok warning page and identify our client
            session.headers.update({
                'ngrok-skip-browser-warning': 'true',
                'User-Agent': 'Backend-API-Client/1.0'
            })
        
        return session

    @swagger_auto_schema(
        operation_summary="List all queries",
        operation_description="Get all queries with optional filtering",
        manual_parameters=[
            openapi.Parameter('session', openapi.IN_QUERY, description="Filter by session ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('viewmode', openapi.IN_QUERY, description="View mode for frames: 'gallery' (flat list) or 'samevideo' (grouped by video)", type=openapi.TYPE_STRING),
            openapi.Parameter('search_url', openapi.IN_QUERY, description="URL of the search server (without /search endpoint)", type=openapi.TYPE_STRING),
            openapi.Parameter('k', openapi.IN_QUERY, description="Number of results to return (default: 10)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('text_weight', openapi.IN_QUERY, description="Weight for text search (default: 0.45)", type=openapi.TYPE_NUMBER),
            openapi.Parameter('ocr_weight', openapi.IN_QUERY, description="Weight for OCR search (default: 0.35)", type=openapi.TYPE_NUMBER),
            openapi.Parameter('image_weight', openapi.IN_QUERY, description="Weight for image search (default: 0.20)", type=openapi.TYPE_NUMBER),
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
        """Get all queries, execute temporal search, and return frames."""
        # --- Phần 1: Lấy và lọc QuerySet ---
        queryset = Query.objects.all()
        session_id = request.query_params.get('session')
        
        if not session_id:
            return Response({"error": "Session ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = queryset.filter(session_id=session_id)
        serializer = QuerySerializer(queryset, many=True, context={'request': request})
        if not queryset.exists():
            return Response({
                'message': 'Temporal search executed successfully',
                'frames': [],
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        search_url = request.query_params.get('search_url')
        k_param = request.query_params.get('k', '10')
        viewmode = request.query_params.get('viewmode', 'gallery')
        
        # Sắp xếp queries theo stage
        sorted_queries = queryset.order_by('stage')
        sorted_queries_serializer = QuerySerializer(sorted_queries, many=True, context={'request': request})        
        # Nếu không có search_url, fallback về OCR search với query có stage lớn nhất
        # if not search_url:
        #     last_query = sorted_queries.last()
        #     if last_query and last_query.ocr and last_query.ocr.strip() and last_query.ocr.lower() != 'null':
        #         ocr_results = self._search_ocr(ocr_text=last_query.ocr, k=int(k_param))
        #         raw_frames = self.adjust_response(request, ocr_results)
        #         frames = self._process_frames_by_viewmode(raw_frames, viewmode)
        #         return Response({
        #             'message': 'OCR search executed successfully',
        #             'frames': frames,
        #             'data': serializer.data,
        #         }, status=status.HTTP_200_OK)
        #     else:
        #         return Response({
        #             'message': 'No valid ocr',
        #             'frames': [],
        #             'data': serializer.data,
        #         }, status=status.HTTP_200_OK)
        
        # --- Phần 2: Chuẩn bị queries_structure và image_files ---
        queries_structure = []
        image_files_to_open = []
        image_counter = 0
        
        for query_data in sorted_queries_serializer.data:
            query_item = {}
            
            # Thêm text nếu có và không rỗng
            if query_data.get('text') and query_data['text'].strip():
                query_item['text'] = query_data['text']
                
            # Thêm ocr nếu có và không rỗng
            if query_data.get('ocr') and query_data['ocr'].strip() and query_data['ocr'].lower() != 'null':
                query_item['ocr'] = query_data['ocr']
            
            # Xử lý image nếu có
            if query_data.get('image'):
                # Tìm query object tương ứng để lấy file path
                query_obj = sorted_queries.get(id=query_data['id'])
                if query_obj.image and hasattr(query_obj.image, 'path'):
                    image_path = query_obj.image.path
                    image_name = os.path.basename(image_path)
                    
                    # Sử dụng tên file thực tế làm image_ref thay vì tạo reference
                    query_item['image_ref'] = image_name
                    image_files_to_open.append((image_name, image_path, image_name))
                    image_counter += 1
            
            # Chỉ thêm vào queries_structure nếu có ít nhất một field
            if query_item:
                queries_structure.append(query_item)
        
        if not queries_structure:
            print("No valid queries with text, ocr, or image content found.")
            return Response({
                'message': 'No valid queries with text, ocr, or image content found.',
                'frames': [],
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        # Chuẩn bị payload
        queries_structure_str = json.dumps(queries_structure)
        
        # Default weights - có thể được override bởi request params
        default_weights = {'text': 0.4, 'ocr': 0.4, 'image': 0.2}
        
        # Cho phép client gửi custom weights qua query params
        weights = {}
        if request.query_params.get('text_weight'):
            weights['text'] = float(request.query_params.get('text_weight'))
        if request.query_params.get('ocr_weight'):
            weights['ocr'] = float(request.query_params.get('ocr_weight'))
        if request.query_params.get('image_weight'):
            weights['image'] = float(request.query_params.get('image_weight'))
        
        # default vector models config
        vector_models_config = [
            {
                "model_name": "ViT-H-14-378-quickgelu",
                "weight": 0.55  
            },
            # {
            #     "model_name": "ViT-H-14-quickgelu",   
            #     "weight": 1
            # },
            {
                "model_name": "ViT-gopt-16-SigLIP2-384",
                "weight": 0.45
            }
        ]
        # Sử dụng default weights nếu không có custom weights
        final_weights = {**default_weights, **weights}
        weights_str = json.dumps(final_weights)
        
        payload = {
            'k': int(k_param),
            'queries_structure': queries_structure_str,
            'weights': weights_str,
            'vector_models_config': json.dumps(vector_models_config),
        }

        # --- Phần 3: Gửi Request và Xử lý Lỗi ---
        files_to_send = []
        opened_files = []
        
        try:
            # Mở các file ảnh cần thiết
            for image_name, path, filename in image_files_to_open:
                f = open(path, 'rb')
                opened_files.append(f)
                # Sử dụng filename thực tế để server có thể match với image_ref
                files_to_send.append(('image_files', (filename, f, 'image/jpeg')))

            # Gửi request POST tới search_url/search
            if not search_url:
                return Response({
                    'message': 'No search URL provided',
                    'frames': [],
                    'data': sorted_queries_serializer.data,
                }, status=status.HTTP_200_OK)
                
            search_endpoint = f"{search_url.rstrip('/')}/search"
            
            # Use helper method to create configured session
            session = self._create_request_session(search_url)
            
            response = session.post(search_endpoint, data=payload, files=files_to_send, timeout=60)
            response.raise_for_status()
            
            search_data = response.json()
            print(f"Search server response: {search_data.get('query_details')}")
            temporal_results = search_data.get('results', [])
            # Xử lý kết quả tương tự như trước
            results = self.adjust_faiss_response(request, temporal_results)
            # flattened_results = self._flatten_temporal_results(temporal_results)
            frames = self._process_frames_by_viewmode(results, viewmode)
            
            return Response({
                'message': 'Temporal search executed successfully',
                'frames': frames,
                'data': serializer.data,
                'search_server_response': search_data
            }, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            print(f"ERROR: Request to search server failed - {e}")
            # Trả về data queries dù có lỗi search
            return Response({
                'message': 'Queries retrieved successfully, but search server failed',
                'data': serializer.data,
                'frames': [],
                'error': 'Failed to communicate with the search server'
            }, status=status.HTTP_200_OK)

        except FileNotFoundError as e:
            print(f"ERROR: Image file not found - {e}")
            # Trả về data queries dù có lỗi file
            return Response({
                'message': 'Queries retrieved successfully, but image file not found', 
                'data': serializer.data,
                'frames': [],
                'error': 'An image file required for the query was not found'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"ERROR: An unexpected error occurred - {e}")
            # Trả về data queries dù có lỗi khác
            return Response({
                'message': 'Queries retrieved successfully, but search failed',
                'data': serializer.data,
                'frames': [],
                'error': 'An unexpected error occurred during search'
            }, status=status.HTTP_200_OK)

        finally:
            # Đảm bảo đóng tất cả các file đã mở
            for f in opened_files:
                f.close()    

    @swagger_auto_schema(
        operation_summary="Synchronize local queries with server",
        operation_description="Batch create/update/delete queries based on localQueries from frontend.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'session': openapi.Schema(type=openapi.TYPE_INTEGER, description="Session ID"),
                'localQueries': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Query ID (optional for new queries)"),
                            'session': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'text': openapi.Schema(type=openapi.TYPE_STRING),
                            'ocr': openapi.Schema(type=openapi.TYPE_STRING),
                            'speech': openapi.Schema(type=openapi.TYPE_STRING),
                            'image': openapi.Schema(type=openapi.TYPE_STRING),
                            'stage': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            }
        ),
        responses={
            200: openapi.Response(
                description="Queries synchronized successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'session': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'text': openapi.Schema(type=openapi.TYPE_STRING),
                                    'ocr': openapi.Schema(type=openapi.TYPE_STRING),
                                    'speech': openapi.Schema(type=openapi.TYPE_STRING),
                                    'image': openapi.Schema(type=openapi.TYPE_STRING),
                                    'stage': openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        )
                    }
                )
            ),
            400: openapi.Response(description="Validation error"),
            404: openapi.Response(description="Session not found")
        }
    )
    def post(self, request):
        """Synchronize localQueries with server database"""
        try:
            print(f"POST request data: {request.data}")
            session_id = request.data.get('session')
            
            # Handle both JSON and FormData requests
            if 'localQueries' in request.data:
                if isinstance(request.data['localQueries'], str):
                    # FormData: localQueries is JSON string
                    import json
                    local_queries = json.loads(request.data['localQueries'])
                else:
                    # JSON: localQueries is already parsed
                    local_queries = request.data.get('localQueries', [])
            else:
                local_queries = []
            
            # Extract image files from FormData (format: image_stage_N)
            image_files = {}
            for key, file in request.FILES.items():
                if key.startswith('image_stage_'):
                    stage = int(key.replace('image_stage_', ''))
                    image_files[stage] = file
            
            print(f"Extracted image files for stages: {list(image_files.keys())}")
            
            if not session_id:
                return Response({
                    'message': 'Session ID is required',
                    'errors': {'session': ['This field is required.']}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get session
            try:
                session = QuerySession.objects.get(id=session_id)
            except QuerySession.DoesNotExist:
                return Response({
                    'message': 'Session not found',
                    'errors': {'session': ['Session does not exist.']}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get all existing queries for this session
            server_queries = Query.objects.filter(session=session).order_by('stage')
            server_queries_dict = {q.id: q for q in server_queries}
            
            # Track operations
            updated_queries = []
            created_queries = []
            local_query_ids = set()
            
            # Process each local query
            for local_query_data in local_queries:
                query_id = local_query_data.get('id')
                
                if query_id and query_id in server_queries_dict:
                    # UPDATE: Query exists on server, check for changes
                    server_query = server_queries_dict[query_id]
                    local_query_ids.add(query_id)
                    
                    # Check if any field has changed
                    changes = {}
                    fields_to_check = ['text', 'ocr', 'speech', 'image', 'stage']
                    
                    for field in fields_to_check:
                        # Skip image field if not present in local_query_data (means no change intended)
                        if field == 'image' and field not in local_query_data:
                            continue
                            
                        local_value = local_query_data.get(field)
                        server_value = getattr(server_query, field)
                        
                        # Handle None values and empty strings
                        local_value = local_value if local_value not in [None, 'null', ''] else None
                        server_value = server_value if server_value not in [None, 'null', ''] else None
                        
                        # Special handling for image field - check for image file in FormData
                        if field == 'image':
                            query_stage = local_query_data.get('stage')
                            if query_stage in image_files:
                                # Use image file from FormData instead of local_value
                                local_value = image_files[query_stage]
                                print(f"Using uploaded image file for existing query {query_id} stage {query_stage}")
                        
                        if local_value != server_value:
                            changes[field] = local_value
                    
                    if changes:
                        # Update the query
                        for field, value in changes.items():
                            setattr(server_query, field, value)
                        server_query.save()
                        updated_queries.append(server_query)
                        
                elif not query_id or query_id not in server_queries_dict:
                    # CREATE: New query (no ID or ID doesn't exist on server)
                    query_stage = local_query_data.get('stage', 1)
                    image_data = local_query_data.get('image')
                    
                    # Use image file from FormData if available for this stage
                    if query_stage in image_files:
                        image_data = image_files[query_stage]
                        print(f"Using uploaded file for stage {query_stage}: {image_data.name}")
                    
                    serializer = QueryCreateSerializer(data={
                        'session': session_id,
                        'text': local_query_data.get('text'),
                        'ocr': local_query_data.get('ocr'), 
                        'speech': local_query_data.get('speech'),
                        'image': image_data,
                        'stage': query_stage,
                    })
                    
                    if serializer.is_valid():
                        new_query = serializer.save()
                        created_queries.append(new_query)
                    else:
                        return Response({
                            'message': 'Failed to create query',
                            'errors': serializer.errors
                        }, status=status.HTTP_400_BAD_REQUEST)
            
            # DELETE: Server queries not present in local queries
            server_query_ids_to_delete = set(server_queries_dict.keys()) - local_query_ids
            deleted_count = 0
            
            if server_query_ids_to_delete:
                deleted_count = Query.objects.filter(
                    id__in=server_query_ids_to_delete,
                    session=session
                ).delete()[0]
            
            # Get final state from database
            final_queries = Query.objects.filter(session=session).order_by('stage')
            response_serializer = QuerySerializer(final_queries, many=True, context={'request': request})
            
            return Response({
                'message': f'Synchronized successfully. Created: {len(created_queries)}, Updated: {len(updated_queries)}, Deleted: {deleted_count}',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'message': 'Error synchronizing queries',
                'errors': {'detail': [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _flatten_temporal_results(
        self, temporal_results: List[List[Tuple[str, float]]],
    ) -> List[Tuple[str, float]]:
        """
        Làm phẳng một danh sách các chuỗi kết quả từ temporal_search thành một danh sách duy nhất.

        Args:
            temporal_results (List[List[Tuple[str, float]]]): 
                Đầu ra từ hàm `temporal_search`, ví dụ: [[chain1], [chain2], ...].

        Returns:
            List[Tuple[str, float]]: Một danh sách phẳng chứa tất cả các khung hình.
        """
        flattened_list = []
        for chain in temporal_results:
            flattened_list.extend(chain)
            
        return flattened_list    
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
            # Return empty list since search service is not configured
            return []
            
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

    def adjust_faiss_response(self, request, results) -> list:
        """
        Adjust FAISS search results to create frames array with full URLs.
        Handles both single list of tuples and list of lists of tuples.
        
        Args:
            request: Django request object
            results: Either:
                - List of tuples: [('L06_V005/14497.jpg', 0.222), ...]
                - List of lists of tuples: [[('L06_V005/14497.jpg', 0.222), ...], ...]
            
        Returns:
            Same structure as input but with frame data dictionaries instead of tuples
        """
        if not results:
            return []
        
        # Get SERVER_IP from environment, fallback to request host
        # server_ip = os.environ.get('SERVER_IP')
        server_ip = None
        if server_ip:
            base_url = f"http://{server_ip}"
        else:
            # Fallback to request host
            host = request.get_host()
            scheme = 'https' if request.is_secure() else 'http'
            base_url = f"{scheme}://{host}"
        
        def convert_tuple_to_frame(result_tuple):
            """Convert single tuple to frame data"""
            # Check if result_tuple is actually a tuple/list and has length
            if not isinstance(result_tuple, (tuple, list)) or len(result_tuple) < 2:
                return None
                
            path = result_tuple[0]  # e.g., "L06_V005/14497.jpg"
            score = result_tuple[1]
            
            # Parse video_name and frame_index from path
            if '/' in path:
                video_name, filename = path.rsplit('/', 1)
                frame_index = filename.replace('.jpg', '')
                
                # Build frame URL
                frame_url = f"{base_url}/media/cframes/{video_name}/{frame_index}.webp"
                
                frame_data = {
                    'url': frame_url,
                    'video_name': video_name,
                    'frame_index': int(frame_index),
                    'score': score
                }
                return frame_data
            return None
        
        # Check if results is a list of lists (2D) or just a list of tuples (1D)
        if results and len(results) > 0 and isinstance(results[0], list):
            # Check if it's 2D (list of lists of tuples) or 1D (list of tuples as lists)
            first_element = results[0]
            if len(first_element) > 0 and isinstance(first_element[0], list) and len(first_element[0]) == 2:
                # 2D format: [[['path1', score1], ['path2', score2]], [...]]
                processed_results = []
                for result_list in results:
                    if isinstance(result_list, list):
                        processed_sublist = []
                        for result_tuple in result_list:
                            frame_data = convert_tuple_to_frame(result_tuple)
                            if frame_data:
                                processed_sublist.append(frame_data)
                        processed_results.append(processed_sublist)
                return processed_results
            elif len(first_element) == 2 and isinstance(first_element[0], str):
                # 1D format: [['path1', score1], ['path2', score2], ...]
                processed_results = []
                for result_tuple in results:
                    frame_data = convert_tuple_to_frame(result_tuple)
                    if frame_data:
                        processed_results.append(frame_data)
                return processed_results
            else:
                # Unknown format, treating as 1D
                processed_results = []
                for result_tuple in results:
                    frame_data = convert_tuple_to_frame(result_tuple)
                    if frame_data:
                        processed_results.append(frame_data)
                return processed_results
        else:
            # Check if it's a flat array with path and score pairs
            # Format: ['L08_V023/16268.jpg', 0.199, 'L08_V024/16269.jpg', 0.188, ...]
            if len(results) >= 2 and isinstance(results[0], str) and isinstance(results[1], (int, float)):
                frames = []
                # Process pairs of (path, score)
                for i in range(0, len(results), 2):
                    if i + 1 < len(results):
                        path = results[i]
                        score = results[i + 1]
                        frame_data = convert_tuple_to_frame((path, score))
                        if frame_data:
                            frames.append(frame_data)
                return frames
            else:
                # Single list of tuples
                frames = []
                for result_tuple in results:
                    frame_data = convert_tuple_to_frame(result_tuple)
                    if frame_data:
                        frames.append(frame_data)
                return frames

    def flatten_frames(self, frames):
        """
        Flatten frames array if it's a list of lists, otherwise return as is.
        
        Args:
            frames: Either flat list of frames or list of lists of frames
            
        Returns:
            Flat list of frames
        """
        if not frames:
            return []
        
        # Check if it's a list of lists by examining the first element
        if frames and len(frames) > 0 and isinstance(frames[0], list):
            # It's a list of lists, flatten it
            flattened = []
            for frame_list in frames:
                if isinstance(frame_list, list):
                    flattened.extend(frame_list)
            return flattened
        else:
            # It's already flat, return as is
            return frames

    def _process_frames_by_viewmode(self, results, view_mode):
        """
        Process frames based on view mode requirements.
        
        Args:
            results: Results from adjust_faiss_response
            view_mode: Either 'gallery' or 'samevideo'
            
        Returns:
            Processed frames according to view mode
        """
        if not results:
            return []
        
        if view_mode == 'gallery':
            # Gallery mode needs flat array
            if results and len(results) > 0 and isinstance(results[0], list):
                # It's a list of lists, flatten it
                return self.flatten_frames(results)
            else:
                # Already flat, return as is
                return results
                
        elif view_mode == 'samevideo':
            # Same video mode needs list of lists grouped by video
            if results and len(results) > 0 and isinstance(results[0], list):
                # Already list of lists, sort each sublist by frame_index
                sorted_results = []
                for sublist in results:
                    if isinstance(sublist, list):
                        # Sort each sublist by frame_index ascending
                        sorted_sublist = sorted(sublist, key=lambda x: x.get('frame_index', 0) if isinstance(x, dict) else 0)
                        sorted_results.append(sorted_sublist)
                    else:
                        sorted_results.append(sublist)
                return sorted_results
            else:
                # Flat array, need to group by video while preserving rank
                if not results:
                    return []
                
                # Group frames by video_name while preserving original order
                video_groups = {}
                video_order = []
                
                for i, frame in enumerate(results):
                    if isinstance(frame, dict):  # Make sure frame is a dictionary
                        video_name = frame.get('video_name')
                        if video_name not in video_groups:
                            video_groups[video_name] = []
                            video_order.append((video_name, i))  # Store video name with first occurrence index
                        video_groups[video_name].append(frame)
                
                # Sort by first occurrence index to maintain rank order
                video_order.sort(key=lambda x: x[1])
                # Build result as list of lists, with each sublist sorted by frame_index
                grouped_results = []
                for video_name, _ in video_order:
                    # Sort frames within each video group by frame_index ascending
                    sorted_group = sorted(video_groups[video_name], key=lambda x: x.get('frame_index', 0) if isinstance(x, dict) else 0)
                    grouped_results.append(sorted_group)
                
                return grouped_results
        
        # Default: return as is
        return results
    
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