import asyncio
import websockets
from google.cloud import speech
import os
import json
import argparse
import sys
import django
from pathlib import Path

# Add Django project to path and setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Now import Django services
from speech.services import WebSocketSpeechHandler

parser = argparse.ArgumentParser(description="Streaming Speech Recognize Server")
parser.add_argument(
    "--key", 
    type=str, 
    default=".env.json",
    help="Path to Google Cloud service account JSON key"
)
parser.add_argument(
    "--port", 
    type=int, 
    default=8000,
    help="Port to run the WebSocket server"
)
args = parser.parse_args()

# --- LƯU Ý BẢO MẬT ---
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.key

HOST = "localhost"
PORT = args.port
LANGUAGE_CODE = "vi-VN"
SAMPLE_RATE = 16000

async def handler(websocket, path):
    """
    WebSocket handler that uses Django-integrated speech handler
    """
    print(f"Client connected: {websocket.remote_address}")
    
    # Use the Django-integrated speech handler
    speech_handler = WebSocketSpeechHandler()
    await speech_handler.handle_client(websocket, path)

async def main():
    print(f"Starting Django-integrated speech server on ws://{HOST}:{PORT}")
    print("This server now integrates with Django models and services")
    async with websockets.serve(handler, HOST, PORT, 
                                ping_interval=20, 
                                ping_timeout=20):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")