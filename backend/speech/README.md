# Speech Recognition App

This Django app provides speech recognition functionality using Google Cloud Speech API with WebSocket support via Django Channels.

## Features

- WebSocket-based real-time speech recognition integrated with Django
- Google Cloud Speech API integration
- Support for Vietnamese and English languages
- Django admin interface for logging
- Runs on the same port as Django backend (no separate server needed)

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Google Cloud credentials**:
   - Place your service account JSON key file in the project root
   - Set environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

3. **Run migrations**:
   ```bash
   python manage.py makemigrations speech
   python manage.py migrate
   ```

4. **Start Django with ASGI server**:
   ```bash
   uvicorn core.asgi:application --host 0.0.0.0 --port 8000
   ```

## Usage

### REST API Endpoint

- `GET /speech/info/` - Get WebSocket connection information

### WebSocket Connection

1. **Connect** to `ws://your-domain/ws/speech/` (via nginx proxy)
2. **Start recognition**:
   ```json
   {"command": "start_recognition"}
   ```
3. **Send audio data** as binary messages
4. **Receive results**:
   ```json
   {
     "transcript": "xin chào",
     "is_final": true
   }
   ```
5. **Stop recognition**:
   ```json
   {"command": "stop_recognition"}
   ```

## Architecture

- **Django Channels**: Handles WebSocket connections
- **Redis**: Channel layer for WebSocket communication
- **Google Cloud Speech API**: Real-time speech recognition
- **Nginx**: Proxy WebSocket connections to Django backend

## Nginx Configuration

The nginx configuration includes WebSocket proxy:
```nginx
location /ws/speech/ {
    proxy_pass http://backend/ws/speech/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    # ... other WebSocket headers
}
```

## Models

### SpeechLog
- `client_ip`: Client IP address
- `transcript_text`: Recognized text
- `is_final`: Whether this is a final result
- `timestamp`: When the transcript was created

## Configuration

Required Django settings:
```python
INSTALLED_APPS = [
    # ...
    'channels',
    'speech',
]

ASGI_APPLICATION = 'core.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/2'],
        },
    },
}
```

## Security Notes

- Ensure Google Cloud credentials are properly secured
- Use HTTPS/WSS in production
- Implement proper authentication for production use
- Consider rate limiting for WebSocket endpoints
- WebSocket runs on same port as Django (port 8000) - no separate server needed
