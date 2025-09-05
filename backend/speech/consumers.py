import asyncio
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from google.cloud import speech
import os

logger = logging.getLogger(__name__)

class SpeechConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.audio_queue = None
        self.recognizing_task = None
        self.language_code = "vi-VN"
        self.sample_rate = 16000
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/backend/speech/lucifer-speech-to-text-api-key.json"  # Ensure credentials are set
    async def connect(self):
        await self.accept()
        logger.info(f"Speech WebSocket connected: {self.scope['client']}")
        
        # Initialize Google Cloud Speech client
        self.client = speech.SpeechAsyncClient()
        self.audio_queue = asyncio.Queue()

    async def disconnect(self, close_code):
        logger.info(f"Speech WebSocket disconnected: {self.scope['client']}")
        await self.cleanup()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                message = json.loads(text_data)
                await self.handle_command(message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
                await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
        elif bytes_data:
            # Audio data received
            if self.recognizing_task and not self.recognizing_task.done():
                await self.audio_queue.put(bytes_data)

    async def handle_command(self, message):
        command = message.get("command")
        
        if command == "start_recognition":
            if not self.recognizing_task or self.recognizing_task.done():
                self.recognizing_task = asyncio.create_task(self.recognize_task())
                logger.info("Started speech recognition")
        elif command == "stop_recognition":
            if self.recognizing_task and not self.recognizing_task.done():
                await self.audio_queue.put(None)  # Stop signal
                logger.info("Stopped speech recognition")

    async def recognize_task(self):
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.sample_rate,
            language_code=self.language_code,
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )

        async def request_generator():
            yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
            try:
                while True:
                    audio_chunk = await self.audio_queue.get()
                    if audio_chunk is None:  # Stop signal
                        break
                    yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
                    self.audio_queue.task_done()
            except Exception as e:
                logger.error(f"Error in request generator: {e}")

        try:
            responses = await self.client.streaming_recognize(requests=request_generator())
            async for response in responses:
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                
                transcript = result.alternatives[0].transcript
                is_final = result.is_final
                
                message = {
                    "transcript": transcript,
                    "is_final": is_final
                }
                await self.send(text_data=json.dumps(message))
        except Exception as e:
            logger.error(f"Error during streaming recognition: {e}")
            await self.send(text_data=json.dumps({"error": str(e)}))
        finally:
            logger.info("Speech recognition task finished")

    async def cleanup(self):
        if self.recognizing_task and not self.recognizing_task.done():
            await self.audio_queue.put(None)
            try:
                await asyncio.wait_for(self.recognizing_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Recognition task did not stop gracefully")
                self.recognizing_task.cancel()
                try:
                    await self.recognizing_task
                except asyncio.CancelledError:
                    pass
