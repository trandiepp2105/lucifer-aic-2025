"""
LangGraph-based video retrieval agent.
This module replaces the LangChain agent with a more structured LangGraph workflow.
"""
import json
import logging
from typing import List, Dict, Any, TypedDict, Optional
import re

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.state import CompiledStateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    logging.warning("LangGraph not available. Please install with: pip install langgraph")
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    CompiledStateGraph = None
    START = "START"
    END = "END"

from .tools import temporal_frame_search_topk, grid_search, valid_video_query, get_video
from .schemas import TemporalSearchInput, GridSearchInput, ValidVideoQueryInput, GetVideoInput
from .utils import robust_json_parse, strip_markdown_code_fences
from .config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoRetrievalState(TypedDict):
    """State definition for the LangGraph video retrieval workflow."""
    query: str
    descriptions: List[str]  # Original user descriptions
    preprocessed_query: str
    temporal_results: Dict[str, Any]
    grid_results: Dict[str, Any]
    validation_results: Dict[str, Any]
    video_clips: List[Dict[str, Any]]
    final_frames: List[str]
    confidence_score: float
    reasoning: str
    success: bool
    error_type: Optional[str]
    error_message: Optional[str]
    intermediate_results: Dict[str, Any]


def preprocess_query_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Preprocess the input query to improve search quality.
    """
    try:
        descriptions = state.get("descriptions", [])
        if not descriptions:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": "No descriptions provided"
            }
        
        # Combine descriptions into a single query
        combined_query = " ".join(descriptions)
        logger.info(f"Preprocessing query: {combined_query[:100]}...")
        
        # Basic preprocessing
        processed = combined_query.strip()
        processed = " ".join(processed.split())
        
        logger.info(f"Preprocessed query: {processed[:100]}...")
        
        return {
            **state,
            "query": combined_query,
            "preprocessed_query": processed,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "preprocessing": {
                    "original_length": len(combined_query), 
                    "processed_length": len(processed)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in preprocess_query_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "preprocessing_error", 
            "error_message": f"Query preprocessing failed: {str(e)}"
        }


def temporal_search_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Perform temporal frame search to find relevant sequences.
    """
    try:
        preprocessed_query = state.get("preprocessed_query", "")
        if not preprocessed_query:
            return {
                **state,
                "success": False,
                "error_type": "temporal_search_error",
                "error_message": "No preprocessed query available"
            }
        
        logger.info("Performing temporal frame search...")
        
        # Prepare temporal search input
        query_sequence = [{"text": preprocessed_query}]
        search_input = TemporalSearchInput(
            query_sequence=query_sequence,
            k=10,
            weights={"text": 1.0, "ocr": 0.8}
        )
        
        # Call temporal search tool
        search_result = temporal_frame_search_topk(search_input.model_dump_json())
        result_data = robust_json_parse(search_result)
        
        if "error" in result_data:
            return {
                **state,
                "success": False,
                "error_type": "temporal_search_error",
                "error_message": result_data["error"]
            }
        
        sequences_found = len(result_data.get('results', []))
        logger.info(f"Temporal search found {sequences_found} sequences")
        
        return {
            **state,
            "temporal_results": result_data,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "temporal_search": {"sequences_found": sequences_found}
            }
        }
        
    except Exception as e:
        logger.error(f"Error in temporal_search_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "temporal_search_error",
            "error_message": f"Temporal search failed: {str(e)}"
        }


def grid_search_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Perform grid search to rank and filter candidate frames.
    """
    try:
        temporal_results = state.get("temporal_results", {})
        if not temporal_results or "results" not in temporal_results:
            return {
                **state,
                "success": False,
                "error_type": "grid_search_error",
                "error_message": "No temporal search results available"
            }
        
        logger.info("Performing grid search for candidate ranking...")
        
        # Extract frame URLs from temporal results
        frame_urls = []
        for result in temporal_results["results"][:5]:  # Top 5 sequences
            frames = result.get("frames", [])
            frame_urls.extend(frames)
        
        if not frame_urls:
            return {
                **state,
                "success": False,
                "error_type": "grid_search_error",
                "error_message": "No frames found in temporal results"
            }
        
        # Prepare grid search input
        query = f"Find the best 3-5 frame candidates matching: {state.get('preprocessed_query', '')}"
        grid_input = GridSearchInput(
            frame_urls=frame_urls[:20],  # Limit to avoid too many frames
            query=query
        )
        
        # Call grid search tool
        grid_result = grid_search(grid_input.model_dump_json())
        result_data = robust_json_parse(grid_result)
        
        if "error" in result_data:
            return {
                **state,
                "success": False,
                "error_type": "grid_search_error",
                "error_message": result_data["error"]
            }
        
        logger.info("Grid search completed successfully")
        
        return {
            **state,
            "grid_results": result_data,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "grid_search": {"frames_analyzed": len(frame_urls)}
            }
        }
        
    except Exception as e:
        logger.error(f"Error in grid_search_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "grid_search_error",
            "error_message": f"Grid search failed: {str(e)}"
        }


def validation_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Validate the best candidates using video validation.
    """
    try:
        grid_results = state.get("grid_results", {})
        if not grid_results:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": "No grid search results available for validation"
            }
        
        logger.info("Performing video validation...")
        
        # Extract the best frame range for video generation
        recommended_frames = grid_results.get("recommended_frames", [])
        if not recommended_frames:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": "No recommended frames from grid search"
            }
        
        # Take the first recommended frame range
        first_frame = recommended_frames[0]
        
        # Extract video name and frame numbers from frame URL
        # Assuming frame URL format: /path/to/video_name/frame_XXXXXX.jpg
        frame_pattern = r'([^/]+)/frame_(\d+)\.jpg'
        match = re.search(frame_pattern, first_frame)
        
        if not match:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": "Could not extract video info from frame URL"
            }
        
        video_name = match.group(1)
        start_frame = int(match.group(2))
        end_frame = start_frame + 30  # Generate ~1 second clip (assuming 30fps)
        
        # Generate video clip
        video_input = GetVideoInput(
            video_name=video_name,
            start_frame=start_frame,
            end_frame=end_frame
        )
        
        video_result = get_video(video_input.model_dump_json())
        video_data = robust_json_parse(video_result)
        
        if "error" in video_data:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": video_data["error"]
            }
        
        clip_url = video_data.get("clip_url", "")
        
        # Validate the video clip
        validation_input = ValidVideoQueryInput(
            video_clip_url=clip_url,
            query_sequence=[{"text": state.get("preprocessed_query", "")}],
            question=f"Does this video clip match the description: {state.get('preprocessed_query', '')}?"
        )
        
        validation_result = valid_video_query(validation_input.model_dump_json())
        validation_data = robust_json_parse(validation_result)
        
        if "error" in validation_data:
            return {
                **state,
                "success": False,
                "error_type": "validation_error",
                "error_message": validation_data["error"]
            }
        
        logger.info("Video validation completed successfully")
        
        return {
            **state,
            "validation_results": validation_data,
            "video_clips": [video_data],
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "validation": {
                    "clip_generated": clip_url,
                    "validation_score": validation_data.get("confidence_score", 0)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in validation_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "validation_error",
            "error_message": f"Validation failed: {str(e)}"
        }


def response_synthesis_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Synthesize the final response with results and reasoning.
    """
    try:
        validation_results = state.get("validation_results", {})
        grid_results = state.get("grid_results", {})
        
        if not validation_results:
            return {
                **state,
                "success": False,
                "error_type": "synthesis_error",
                "error_message": "No validation results available for synthesis"
            }
        
        logger.info("Synthesizing final response...")
        
        # Extract final results
        is_match = validation_results.get("is_match", False)
        confidence_score = validation_results.get("confidence_score", 0.0)
        validation_reasoning = validation_results.get("reasoning", "")
        
        # Get recommended frames from grid search
        recommended_frames = grid_results.get("recommended_frames", [])
        
        # Build reasoning
        reasoning_parts = []
        if grid_results.get("grid_analysis"):
            reasoning_parts.append(f"Grid Analysis: {grid_results['grid_analysis']}")
        if validation_reasoning:
            reasoning_parts.append(f"Validation: {validation_reasoning}")
        
        final_reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Analysis completed successfully"
        
        if is_match and confidence_score >= 0.5:
            return {
                **state,
                "success": True,
                "final_frames": recommended_frames[:5],  # Return top 5 frames
                "confidence_score": confidence_score,
                "reasoning": final_reasoning,
                "error_type": None,
                "error_message": None
            }
        else:
            return {
                **state,
                "success": False,
                "error_type": "no_match",
                "error_message": f"No suitable video found. Confidence: {confidence_score:.2f}",
                "final_frames": [],
                "confidence_score": confidence_score,
                "reasoning": final_reasoning
            }
        
    except Exception as e:
        logger.error(f"Error in response_synthesis_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "synthesis_error",
            "error_message": f"Response synthesis failed: {str(e)}"
        }


def error_handler_node(state: VideoRetrievalState) -> VideoRetrievalState:
    """
    Node: Handle errors and provide fallback responses.
    """
    error_type = state.get("error_type", "unknown")
    error_message = state.get("error_message", "Unknown error occurred")
    
    logger.error(f"Error handler activated: {error_type} - {error_message}")
    
    return {
        **state,
        "success": False,
        "final_frames": [],
        "confidence_score": 0.0,
        "reasoning": f"Error occurred during processing: {error_message}"
    }


# Conditional edge functions
def should_continue_to_grid_search(state: VideoRetrievalState) -> str:
    """Conditional edge: Determine if temporal search was successful enough to continue."""
    temporal_results = state.get("temporal_results", {})
    if temporal_results and "results" in temporal_results and len(temporal_results["results"]) > 0:
        return "grid_search"
    else:
        return "end_error"


def should_continue_to_validation(state: VideoRetrievalState) -> str:
    """Conditional edge: Determine if grid search was successful enough to continue."""
    grid_results = state.get("grid_results", {})
    if grid_results and grid_results.get("recommended_frames"):
        return "validation"
    else:
        return "end_error"


def should_continue_to_synthesis(state: VideoRetrievalState) -> str:
    """Conditional edge: Determine if validation was completed."""
    validation_results = state.get("validation_results", {})
    if validation_results:
        return "synthesis"
    else:
        return "end_error"


def create_langgraph_workflow() -> CompiledStateGraph:
    """
    Create and compile the LangGraph workflow for video retrieval.
    
    Returns:
        Compiled LangGraph workflow ready for execution
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph is not available. Please install with: pip install langgraph")
    
    # Create the workflow graph
    workflow = StateGraph(VideoRetrievalState)
    
    # Add nodes
    workflow.add_node("preprocess", preprocess_query_node)
    workflow.add_node("temporal_search", temporal_search_node)
    workflow.add_node("grid_search", grid_search_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("synthesis", response_synthesis_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Set entry point
    workflow.set_entry_point("preprocess")
    
    # Add edges
    workflow.add_edge("preprocess", "temporal_search")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "temporal_search",
        should_continue_to_grid_search,
        {
            "grid_search": "grid_search",
            "end_error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "grid_search", 
        should_continue_to_validation,
        {
            "validation": "validation",
            "end_error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "validation",
        should_continue_to_synthesis,
        {
            "synthesis": "synthesis",
            "end_error": "error_handler"
        }
    )
    
    # Add finish edges
    workflow.add_edge("synthesis", END)
    workflow.add_edge("error_handler", END)
    
    # Compile the workflow
    compiled_workflow = workflow.compile()
    
    logger.info("LangGraph workflow compiled successfully")
    return compiled_workflow


class LangGraphVideoAgent:
    """
    LangGraph-based video retrieval agent that replaces the LangChain implementation.
    """
    
    def __init__(self):
        """Initialize the LangGraph agent."""
        self.workflow = None
        self._setup_workflow()
    
    def _setup_workflow(self):
        """Setup the LangGraph workflow."""
        try:
            self.workflow = create_langgraph_workflow()
            logger.info("LangGraph video agent initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up LangGraph workflow: {str(e)}")
            raise
    
    def find_video(self, descriptions: List[str]) -> Dict[str, Any]:
        """
        Find video clips matching the given descriptions.
        
        Args:
            descriptions: List of natural language descriptions
            
        Returns:
            Dictionary with search results matching the existing API format
        """
        try:
            # Prepare initial state
            initial_state = VideoRetrievalState(
                query="",
                descriptions=descriptions,
                preprocessed_query="",
                temporal_results={},
                grid_results={},
                validation_results={},
                video_clips=[],
                final_frames=[],
                confidence_score=0.0,
                reasoning="",
                success=False,
                error_type=None,
                error_message=None,
                intermediate_results={}
            )
            
            # Execute the workflow
            logger.info(f"Starting LangGraph workflow for descriptions: {descriptions}")
            
            result = self.workflow.invoke(initial_state)
            
            # Format response to match existing API
            if result.get("success"):
                return {
                    "success": True,
                    "frames": result.get("final_frames", []),
                    "confidence_score": result.get("confidence_score", 0.0),
                    "reasoning": result.get("reasoning", ""),
                    "intermediate_results": result.get("intermediate_results", {})
                }
            else:
                return {
                    "success": False,
                    "error_type": result.get("error_type", "unknown"),
                    "error_message": result.get("error_message", "Unknown error"),
                    "frames": [],
                    "confidence_score": result.get("confidence_score", 0.0),
                    "reasoning": result.get("reasoning", "")
                }
                
        except Exception as e:
            logger.error(f"Error in LangGraph workflow execution: {str(e)}")
            return {
                "success": False,
                "error_type": "workflow_error",
                "error_message": f"Workflow execution failed: {str(e)}",
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": f"Workflow error: {str(e)}"
            }


# Global instance for backwards compatibility
_langgraph_agent_instance = None


def get_langgraph_agent() -> LangGraphVideoAgent:
    """
    Get the global LangGraph agent instance.
    
    Returns:
        LangGraphVideoAgent instance
    """
    global _langgraph_agent_instance
    if _langgraph_agent_instance is None:
        _langgraph_agent_instance = LangGraphVideoAgent()
    return _langgraph_agent_instance
