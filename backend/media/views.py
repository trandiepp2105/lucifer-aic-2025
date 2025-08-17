import os
import json
import subprocess
import logging
import requests
from pathlib import Path
from django.http import JsonResponse
from django.views import View
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

logger = logging.getLogger(__name__)


def get_video_metadata(video_name, base_url="http://nginx"):
    """
    Lấy metadata của video qua HTTP API thay vì đọc trực tiếp từ file system.
    
    Args:
        video_name (str): Tên video (ví dụ: L05_V010)
        base_url (str): Base URL của nginx server
    
    Returns:
        dict: Metadata của video hoặc None nếu không tìm thấy
    """
    try:
        metadata_url = f"{base_url}/media/frames/{video_name}/metadata.json"
        response = requests.get(metadata_url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Metadata not found for {video_name} at {metadata_url}. Status: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching metadata for {video_name}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing metadata JSON for {video_name}: {e}")
        return None


def find_hls_playlist(video_name, base_url="http://nginx"):
    """
    Tìm HLS playlist (.m3u8) qua HTTP API và trả về đường dẫn local để ffmpeg sử dụng.
    
    Args:
        video_name (str): Tên video (ví dụ: L05_V010)
        base_url (str): Base URL của nginx server để kiểm tra file tồn tại
    
    Returns:
        str: Local file system path của HLS playlist hoặc None nếu không tìm thấy
    """
    hls_path = os.environ.get('HLS_PATH', '/media/videos_hls')
    
    try:
        # Kiểm tra HLS playlist tồn tại qua HTTP
        playlist_url = f"{base_url}/media/videos_hls/{video_name}/playlist.m3u8"
        response = requests.head(playlist_url, timeout=10)
        
        if response.status_code == 200:
            # Nếu HLS playlist tồn tại trên nginx, trả về local path cho ffmpeg
            local_path = Path(hls_path) / video_name / "playlist.m3u8"
            logger.info(f"Found HLS playlist via HTTP: {playlist_url}, using local path: {local_path}")
            return str(local_path)
            
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error checking HLS playlist for {video_name}: {e}")
    
    logger.warning(f"No HLS playlist found for {video_name}")
    return None


@method_decorator(csrf_exempt, name='dispatch')
class VideoClipAPIView(APIView):
    """
    API endpoint để tạo video clip từ frame range.
    """
    
    @swagger_auto_schema(
        operation_summary="Tạo video clip từ frame range",
        operation_description="Tạo một video clip từ frame bắt đầu đến frame kết thúc cho một video cụ thể",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'video_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Tên video (ví dụ: L01_V001)"
                ),
                'start_frame': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Frame bắt đầu"
                ),
                'end_frame': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Frame kết thúc"
                ),
            },
            required=['video_name', 'start_frame', 'end_frame']
        ),
        responses={
            200: openapi.Response(
                description="Video clip được tạo thành công",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'clip_url': openapi.Schema(type=openapi.TYPE_STRING, description="URL của video clip"),
                        'duration': openapi.Schema(type=openapi.TYPE_NUMBER, description="Thời lượng clip (giây)"),
                        'start_time': openapi.Schema(type=openapi.TYPE_NUMBER, description="Thời gian bắt đầu (giây)"),
                        'end_time': openapi.Schema(type=openapi.TYPE_NUMBER, description="Thời gian kết thúc (giây)"),
                        'cached': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Clip có được cache từ trước không"),
                    }
                )
            ),
            400: openapi.Response(description="Dữ liệu đầu vào không hợp lệ"),
            404: openapi.Response(description="Video hoặc metadata không tìm thấy"),
            500: openapi.Response(description="Lỗi server khi tạo video clip")
        }
    )
    def post(self, request):
        """Tạo video clip từ frame range."""
        try:
            # Lấy dữ liệu từ request
            data = request.data
            video_name = data.get('video_name')
            start_frame = data.get('start_frame')
            end_frame = data.get('end_frame')
            
            # Validate input
            if not all([video_name, start_frame is not None, end_frame is not None]):
                return Response({
                    'error': 'Thiếu tham số bắt buộc: video_name, start_frame, end_frame'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                start_frame = int(start_frame)
                end_frame = int(end_frame)
            except (ValueError, TypeError):
                return Response({
                    'error': 'start_frame và end_frame phải là số nguyên'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if start_frame >= end_frame:
                return Response({
                    'error': 'start_frame phải nhỏ hơn end_frame'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Lấy metadata qua HTTP API
            metadata = get_video_metadata(video_name)
            fps = 25  # Default fps
            
            if metadata:
                fps = metadata.get('fps', 25)
                logger.info(f"Retrieved metadata for {video_name}: fps={fps}")
            else:
                logger.warning(f"Using default fps={fps} for {video_name}")
            
            # Tính thời gian start và end
            start_time = start_frame / fps
            end_time = end_frame / fps
            duration = end_time - start_time
            
            # Tìm HLS playlist
            source_video_path = find_hls_playlist(video_name)
            
            if not source_video_path:
                return Response({
                    'error': f'Không tìm thấy HLS playlist cho video {video_name}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Tạo output directory cho clips
            clips_dir = Path(settings.MEDIA_ROOT) / 'video_clips'
            clips_dir.mkdir(exist_ok=True)
            
            # Tạo tên file cho clip
            clip_filename = f"{video_name}_f{start_frame}-{end_frame}.mp4"
            output_path = clips_dir / clip_filename
            
            # Nếu clip đã tồn tại, trả về luôn
            if output_path.exists():
                clip_url = f"/media/video_clips/{clip_filename}"
                return Response({
                    'success': True,
                    'clip_url': clip_url,
                    'duration': duration,
                    'start_time': start_time,
                    'end_time': end_time,
                    'cached': True
                })
            
            # Sử dụng ffmpeg để tạo clip từ HLS với stream copy để nhanh hơn
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', source_video_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c', 'copy',  # Stream copy nhanh hơn
                '-avoid_negative_ts', 'make_zero',  # Tránh timestamp âm
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            # Chạy ffmpeg
            logger.info(f"Executing ffmpeg with HLS: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=60  # Timeout 60s
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return Response({
                    'error': f'Lỗi khi tạo video clip: {result.stderr}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Kiểm tra file output đã được tạo
            if not output_path.exists():
                return Response({
                    'error': 'Video clip được tạo nhưng không tìm thấy file output'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Trả về URL của clip
            clip_url = f"/media/video_clips/{clip_filename}"
            
            return Response({
                'success': True,
                'clip_url': clip_url,
                'duration': duration,
                'start_time': start_time,
                'end_time': end_time,
                'cached': False
            })
            
        except subprocess.TimeoutExpired:
            return Response({
                'error': 'Timeout khi tạo video clip'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error in VideoClipAPIView: {str(e)}")
            return Response({
                'error': f'Lỗi server: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
