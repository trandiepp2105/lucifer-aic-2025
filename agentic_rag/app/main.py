"""
FastAPI application for the Agentic RAG Video Retrieval system.
"""
import logging
from typing import Union

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .schemas import VideoSearchRequest, VideoSearchResponse, ErrorResponse
from .agent_core import get_agent
from .monitoring import get_monitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Agent thông minh tự động hóa quy trình truy xuất video dựa trên mô tả ngôn ngữ tự nhiên",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    try:
        logger.info("Starting up Agentic RAG Video Retrieval API...")
        
        # Validate configuration
        config.validate_config()
        logger.info("Configuration validated successfully")
        
        # Initialize agent (this will create the global instance)
        agent = get_agent()
        logger.info("Agent initialized successfully")
        
        logger.info("Startup completed successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise


@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "Agentic RAG Video Retrieval API",
        "version": config.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Basic health check - could be expanded to check external dependencies
        return {
            "status": "healthy",
            "version": config.APP_VERSION,
            "timestamp": "2025-07-27"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )


@app.post(
    "/find-video",
    response_model=Union[VideoSearchResponse, ErrorResponse],
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm video dựa trên mô tả",
    description="Endpoint chính để tìm kiếm video phù hợp với mô tả bằng ngôn ngữ tự nhiên"
)
async def find_video(request: VideoSearchRequest) -> Union[VideoSearchResponse, ErrorResponse]:
    """
    Tìm kiếm video dựa trên mô tả bằng ngôn ngữ tự nhiên.
    
    Args:
        request: VideoSearchRequest chứa mô tả video cần tìm
        
    Returns:
        VideoSearchResponse nếu thành công hoặc ErrorResponse nếu lỗi
        
    Raises:
        HTTPException: Với các lỗi HTTP tương ứng
    """
    try:
        logger.info(f"Received video search request: {request.descriptions}")
        
        # Get agent instance
        agent = get_agent()
        
        # Execute video search
        result = agent.find_video(request.descriptions)
        
        if result["success"]:
            # Return successful response
            response = VideoSearchResponse(
                success=True,
                frames=result["frames"],
                confidence_score=result["confidence_score"],
                reasoning=result["reasoning"]
            )

            logger.info(f"Successfully found video: {result['frames']}")
            return response
            
        else:
            # Return error response with appropriate HTTP status
            error_response = ErrorResponse(
                success=False,
                error_type=result.get("error_type", "unknown"),
                error_message=result.get("error_message", "Unknown error")
            )
            
            # Different HTTP status codes based on error type
            error_type = result.get("error_type", "unknown")
            if error_type == "no_match":
                status_code = status.HTTP_404_NOT_FOUND
            elif error_type == "system_error":
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            elif error_type == "parsing_error":
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            logger.warning(f"Video search failed: {error_response.error_message}")
            
            return JSONResponse(
                status_code=status_code,
                content=error_response.dict()
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in find_video endpoint: {str(e)}")
        
        error_response = ErrorResponse(
            success=False,
            error_type="system_error",
            error_message=f"Lỗi hệ thống không xác định: {str(e)}"
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.dict()
        )


@app.get("/agent/status")
async def agent_status():
    """Get current agent status and configuration."""
    try:
        agent = get_agent()
        
        return {
            "agent_initialized": agent is not None,
            "model": config.GEMINI_MODEL,
            "api_endpoints": {
                "search_api": config.SEARCH_API_URL,
                "media_api": config.MEDIA_API_URL
            },
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Error getting agent status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting agent status: {str(e)}"
        )


@app.get("/monitoring/sessions")
async def get_monitoring_sessions():
    """Get list of all monitoring sessions."""
    try:
        monitor = get_monitor()
        sessions = monitor.list_sessions()
        return {
            "success": True,
            "sessions": sessions,
            "total_count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Error getting monitoring sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting monitoring sessions: {str(e)}"
        )


@app.get("/monitoring/sessions/{session_id}")
async def get_monitoring_session(session_id: str):
    """Get detailed information about a specific monitoring session."""
    try:
        monitor = get_monitor()
        session = monitor.load_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return {
            "success": True,
            "session": session.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting monitoring session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting monitoring session: {str(e)}"
        )


@app.get("/monitoring/current")
async def get_current_monitoring_session():
    """Get current active monitoring session."""
    try:
        monitor = get_monitor()
        current_session = monitor.get_current_session()
        
        if not current_session:
            return {
                "success": True,
                "has_active_session": False,
                "session": None
            }
        
        return {
            "success": True,
            "has_active_session": True,
            "session": current_session.to_dict()
        }
    except Exception as e:
        logger.error(f"Error getting current monitoring session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting current monitoring session: {str(e)}"
        )


@app.post("/monitoring/export/{session_id}")
async def export_monitoring_session(session_id: str, format: str = "json"):
    """Export a monitoring session in specified format."""
    try:
        monitor = get_monitor()
        
        if format not in ["json", "html"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be 'json' or 'html'"
            )
        
        export_path = monitor.export_session(session_id, format)
        
        if not export_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or export failed"
            )
        
        return {
            "success": True,
            "export_path": export_path,
            "format": format
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting monitoring session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting monitoring session: {str(e)}"
        )


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    logger.error(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error_type": "validation_error",
            "error_message": str(exc)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_type": "system_error", 
            "error_message": "Internal server error"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.DEBUG,
        log_level="info"
    )
