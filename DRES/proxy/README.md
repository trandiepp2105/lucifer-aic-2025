# DRES Proxy Service

## Overview
This proxy service acts as an intermediary between clients and the DRES system, providing public access through ngrok tunneling.

## Architecture
```
Client --> Ngrok Tunnel --> Proxy Service --> DRES Service
```

## Features
- FastAPI-based proxy server
- Automatic ngrok tunnel creation for public access
- Forward all HTTP methods (GET, POST, PUT, DELETE, etc.)
- Preserve request headers, query parameters, and body
- Health check endpoint
- Error handling and logging

## Configuration
Environment variables are defined in `.env`:
- `NGROK_AUTHTOKEN`: Your ngrok authentication token
- `DRES_HOST`: DRES service hostname (default: dres)
- `DRES_PORT`: DRES service port (default: 8080)
- `PROXY_PORT`: Proxy service port (default: 8088)

## Usage

### Start Services
```bash
# Start both DRES and Proxy services
docker-compose up -d

# View logs
docker-compose logs -f proxy
```

### Stop Services
```bash
docker-compose down
```

### Health Check
```bash
curl http://localhost:8088/health
```

## Endpoints
- `GET /health` - Health check endpoint
- `/{path:path}` - Proxy all requests to DRES service

## Public Access
Once started, the proxy service will automatically create an ngrok tunnel and display the public URL in the logs:
```
🌐 Ngrok tunnel created: https://abc123.ngrok.io
🔗 Public URL: https://abc123.ngrok.io
```

Clients can access DRES through this public URL instead of direct localhost access.

## Dependencies
- FastAPI - Web framework
- uvicorn - ASGI server
- httpx - HTTP client for forwarding requests
- nest-asyncio - Handle nested event loops
- pyngrok - Ngrok Python integration
- python-multipart - Handle multipart requests
