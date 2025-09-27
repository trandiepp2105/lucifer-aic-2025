import os
import asyncio
import nest_asyncio
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import httpx
from pyngrok import ngrok
import threading
import time

# Apply nest_asyncio to handle nested event loops
nest_asyncio.apply()

# Get configuration from environment variables
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN")
DRES_HOST = os.getenv("DRES_HOST", "dres")
DRES_PORT = int(os.getenv("DRES_PORT", "8080"))
PROXY_PORT = int(os.getenv("PROXY_PORT", "8088"))

# DRES base URL
DRES_BASE_URL = f"http://{DRES_HOST}:{DRES_PORT}"

print(f"DRES_BASE_URL: {DRES_BASE_URL}")
print(f"Proxy will run on port: {PROXY_PORT}")

# Global variable to store ngrok public URL
ngrok_public_url = None

# HTTP client for forwarding requests
http_client = httpx.AsyncClient(timeout=60.0)

def setup_ngrok():
    """Setup ngrok tunnel"""
    global ngrok_public_url
    try:
        if NGROK_AUTHTOKEN:
            ngrok.set_auth_token(NGROK_AUTHTOKEN)
            
        # Create HTTP tunnel
        tunnel = ngrok.connect(PROXY_PORT)
        public_url = tunnel.public_url
        ngrok_public_url = public_url
        print(f"🌐 Ngrok tunnel created: {public_url}")
        print(f"🔗 Public URL: {public_url}")
        return public_url
    except Exception as e:
        print(f"❌ Failed to create ngrok tunnel: {e}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup - no ngrok setup here, it's handled in main
    yield
    
    # Shutdown
    await http_client.aclose()
    try:
        ngrok.disconnect(f"http://localhost:{PROXY_PORT}")
    except:
        pass

app = FastAPI(
    title="DRES Proxy Service", 
    description="Proxy service for DRES system",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "dres-proxy"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_request(request: Request, path: str):
    """
    Proxy all requests to DRES service
    """
    try:
        # Build target URL
        target_url = f"{DRES_BASE_URL}/{path}"
        
        # Get request body
        body = await request.body()
        
        # Prepare headers (exclude host header to avoid conflicts)
        headers = dict(request.headers)
        headers.pop("host", None)
        
        # Get query parameters
        query_params = str(request.query_params) if request.query_params else ""
        if query_params:
            target_url += f"?{query_params}"
        
        print(f"🔄 Proxying {request.method} {target_url}")
        
        # Forward request to DRES
        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            follow_redirects=True
        )
        
        # Prepare response headers
        response_headers = dict(response.headers)
        # Remove headers that might cause issues
        response_headers.pop("content-encoding", None)
        response_headers.pop("transfer-encoding", None)
        
        # Return response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type")
        )
        
    except httpx.ConnectError as e:
        print(f"❌ Connection error to DRES: {e}")
        return Response(
            content=f"Unable to connect to DRES service: {e}",
            status_code=502,
            media_type="text/plain"
        )
    except Exception as e:
        print(f"❌ Proxy error: {e}")
        return Response(
            content=f"Proxy error: {e}",
            status_code=500,
            media_type="text/plain"
        )

if __name__ == "__main__":
    print("🚀 Starting DRES Proxy Service...")
    print(f"📡 Forwarding requests to: {DRES_BASE_URL}")
    
    # Setup ngrok tunnel
    public_url = setup_ngrok()
    if public_url:
        print(f"🔗 Ngrok Public URL: {public_url}")
    else:
        print("⚠️ Running without ngrok tunnel")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PROXY_PORT,
        log_level="info"
    )
