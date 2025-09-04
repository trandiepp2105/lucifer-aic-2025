import asyncio
import websockets
import json
import logging
from google.cloud import speech
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

logger = logging.getLogger(__name__)

# Global variables for WebSocket server
LANGUAGE_CODE = "vi-VN"
SAMPLE_RATE = 16000
HOST = os.environ.get('HOST', '127.0.0.1')
@csrf_exempt
def websocket_info(request):
    """
    Simple endpoint to get WebSocket connection information
    """
    if request.method == 'GET':
        # Use nginx proxy path for WebSocket - same port as Django
        websocket_url = f'ws://{HOST}/ws/speech/'
        
        return JsonResponse({
            'websocket_url': websocket_url,
            'supported_languages': ['vi-VN', 'en-US'],
            'sample_rate': SAMPLE_RATE,
            'encoding': 'LINEAR16',
            'status': 'ready',
            'implementation': 'Django Channels'
        })
    else:
        return JsonResponse({'error': 'Only GET method allowed'}, status=405)
