"""
LangGraph implementation for video retrieval pipeline.
Converts the existing LangChain pipeline into a LangGraph workflow with improved
retrieval quality, maintainability, and parallel processing capabilities.
"""
import json
import logging
import asyncio
from typing import List, Dict, Any, TypedDict, Union, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.state import CompiledStateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    logging.warning("LangGraph not available. Please install with: pip install langgraph")
    LANGGRAPH_AVAILABLE = False
    # Define dummy classes for type hints
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


class SearchState(TypedDict):
    """State definition for the LangGraph search workflow."""
    query: str
    descriptions: List[str]  # Original user descriptions
    preprocessed_query: str
    search_modes: List[str]  # e.g., ["text", "ocr", "image"]
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


def preprocess_query_node(state: SearchState) -> SearchState:
    """
    Node: Preprocess the input query to improve search quality.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with preprocessed query
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
        
        # Detect search modes based on content
        search_modes = ["text"]  # Default to text search
        if any(keyword in processed.lower() for keyword in ["text", "writing", "words"]):
            search_modes.append("ocr")
        
        logger.info(f"Preprocessed query: {processed[:100]}...")
        
        return {
            **state,
            "query": combined_query,
            "preprocessed_query": processed,
            "search_modes": search_modes,
            "intermediate_results": {"preprocessing": {"original_length": len(combined_query), "processed_length": len(processed)}}
        }
        
    except Exception as e:
        logger.error(f"Error in preprocess_query_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "preprocessing_error", 
            "error_message": f"Query preprocessing failed: {str(e)}"
        }


def temporal_search_node(state: SearchState) -> SearchState:
    """
    Node: Perform temporal frame search to find relevant sequences.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with temporal search results
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
        
        logger.info(f"Temporal search found {len(result_data.get('results', []))} sequences")
        
        return {
            **state,
            "temporal_results": result_data,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "temporal_search": {"sequences_found": len(result_data.get("results", []))}
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


def grid_search_node(state: SearchState) -> SearchState:
    """
    Node: Perform grid search to rank and filter candidate frames.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with grid search results
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


def validation_node(state: SearchState) -> SearchState:
    """
    Node: Validate the best candidates using video validation.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with validation results
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


def response_synthesis_node(state: SearchState) -> SearchState:
    """
    Node: Synthesize the final response with results and reasoning.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with final response
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


def should_continue_to_grid_search(state: SearchState) -> str:
    """Conditional edge: Determine if temporal search was successful enough to continue."""
    temporal_results = state.get("temporal_results", {})
    if temporal_results and "results" in temporal_results and len(temporal_results["results"]) > 0:
        return "grid_search"
    else:
        return "end_error"


def should_continue_to_validation(state: SearchState) -> str:
    """Conditional edge: Determine if grid search was successful enough to continue."""
    grid_results = state.get("grid_results", {})
    if grid_results and grid_results.get("recommended_frames"):
        return "validation"
    else:
        return "end_error"


def should_continue_to_synthesis(state: SearchState) -> str:
    """Conditional edge: Determine if validation was completed."""
    validation_results = state.get("validation_results", {})
    if validation_results:
        return "synthesis"
    else:
        return "end_error"


def error_handler_node(state: SearchState) -> SearchState:
    """
    Node: Handle errors and provide fallback responses.
    
    Args:
        state: Current workflow state with error information
        
    Returns:
        Updated state with error handling
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


def create_langgraph_workflow():
    """
    Create and compile the LangGraph workflow for video retrieval.
    
    Returns:
        Compiled LangGraph workflow ready for execution
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("LangGraph is not available. Please install with: pip install langgraph")
    
    # Create the workflow graph
    workflow = StateGraph(SearchState)
    
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
            initial_state = SearchState(
                query="",
                descriptions=descriptions,
                preprocessed_query="",
                search_modes=[],
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


@dataclass
class ClipHit:
    """Data structure representing a video clip hit from search results."""
    id: str
    score: float
    url: str
    video_name: str = ""
    start_frame: int = 0
    end_frame: int = 0
    frames: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.frames is None:
            self.frames = []
        if self.metadata is None:
            self.metadata = {}


class SearchState(TypedDict):
    """State definition for the LangGraph search workflow."""
    query: str
    descriptions: List[str]  # Original user descriptions
    preprocessed_query: str
    search_modes: List[str]  # e.g., ["text", "ocr", "image"]
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


def preprocess_query_node(state: SearchState) -> SearchState:
    """
    Node: Preprocess the input query to improve search quality.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with preprocessed query
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
        
        # Detect search modes based on content
        search_modes = ["text"]  # Default to text search
        if any(keyword in processed.lower() for keyword in ["text", "writing", "words"]):
            search_modes.append("ocr")
        
        logger.info(f"Preprocessed query: {processed[:100]}...")
        
        return {
            **state,
            "query": combined_query,
            "preprocessed_query": processed,
            "search_modes": search_modes,
            "intermediate_results": {"preprocessing": {"original_length": len(combined_query), "processed_length": len(processed)}}
        }
        
    except Exception as e:
        logger.error(f"Error in preprocess_query_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_type": "preprocessing_error", 
            "error_message": f"Query preprocessing failed: {str(e)}"
        }


def temporal_search_node(state: SearchState) -> SearchState:
    """
    Node: Perform temporal frame search to find relevant sequences.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with temporal search results
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
        
        logger.info(f"Temporal search found {len(result_data.get('results', []))} sequences")
        
        return {
            **state,
            "temporal_results": result_data,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "temporal_search": {"sequences_found": len(result_data.get("results", []))}
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


def grid_search_node(state: SearchState) -> SearchState:
    """
    Node: Perform grid search to rank and filter candidate frames.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with grid search results
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


def validation_node(state: SearchState) -> SearchState:
    """
    Node: Validate the best candidates using video validation.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with validation results
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
        import re
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


def response_synthesis_node(state: SearchState) -> SearchState:
    """
    Node: Synthesize the final response with results and reasoning.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with final response
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


def should_continue_to_grid_search(state: SearchState) -> str:
    """Conditional edge: Determine if temporal search was successful enough to continue."""
    temporal_results = state.get("temporal_results", {})
    if temporal_results and "results" in temporal_results and len(temporal_results["results"]) > 0:
        return "grid_search"
    else:
        return "end_error"


def should_continue_to_validation(state: SearchState) -> str:
    """Conditional edge: Determine if grid search was successful enough to continue."""
    grid_results = state.get("grid_results", {})
    if grid_results and grid_results.get("recommended_frames"):
        return "validation"
    else:
        return "end_error"


def should_continue_to_synthesis(state: SearchState) -> str:
    """Conditional edge: Determine if validation was completed."""
    validation_results = state.get("validation_results", {})
    if validation_results:
        return "synthesis"
    else:
        return "end_error"


def error_handler_node(state: SearchState) -> SearchState:
    """
    Node: Handle errors and provide fallback responses.
    
    Args:
        state: Current workflow state with error information
        
    Returns:
        Updated state with error handling
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


def embed_search_api(query: str, modes: List[str], k: int = 10) -> List[ClipHit]:
    """
    Search for clips using temporal API with specified modes.
    
    Args:
        query: Search query string
        modes: List of search modes (text, ocr, image)
        k: Number of results to return
        
    Returns:
        List of ClipHit objects representing search results
    """
    logger.info(f"Embed search with modes {modes} for query: {query[:100]}...")
    
    try:
        # Convert the query into a temporal search format
        # For simplicity, we'll create a single stage query
        query_sequence = []
        
        for mode in modes:
            stage = {}
            if mode == "text":
                stage["text"] = query
            elif mode == "ocr":
                stage["ocr"] = query
            # For image mode, we'd need image data - skip for now
            
            if stage:
                query_sequence.append(stage)
        
        if not query_sequence:
            # Fallback to text search
            query_sequence = [{"text": query}]
        
        # Prepare input for temporal search
        search_input = TemporalSearchInput(
            query_sequence=query_sequence,
            k=k
        )
        
        # Call the existing temporal search function
        result_str = temporal_frame_search_topk(search_input.json())
        result_data = robust_json_parse(result_str)
        
        if "error" in result_data:
            logger.error(f"Search API error: {result_data['error']}")
            return []
        
        # Convert results to ClipHit objects
        hits = []
        results = result_data.get("results", [])
        
        for i, result in enumerate(results):
            if isinstance(result, dict):
                frames = result.get("frames", [])
                score = result.get("sequence_score", 0.0)
                
                # Extract video info from first frame if available
                video_name = ""
                start_frame = 0
                end_frame = 0
                
                if frames:
                    # Parse frame URL to extract video info
                    # Assuming format like "L01_V001_frame_123.jpg"
                    first_frame = frames[0]
                    if "_frame_" in first_frame:
                        parts = first_frame.split("_frame_")
                        if len(parts) >= 2:
                            video_name = parts[0].split("/")[-1]  # Get last part of path
                            try:
                                start_frame = int(parts[1].split(".")[0])
                                end_frame = start_frame + len(frames)
                            except:
                                pass
                
                hit = ClipHit(
                    id=f"hit_{i}",
                    score=score,
                    url="",  # Will be filled during verification
                    video_name=video_name,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    frames=frames,
                    metadata=result
                )
                hits.append(hit)
        
        logger.info(f"Found {len(hits)} search hits")
        return hits
        
    except Exception as e:
        logger.error(f"Error in embed_search_api: {str(e)}")
        return []


def verify_clip(clip: ClipHit) -> bool:
    """
    Verify if a clip hit is relevant and of good quality.
    
    Args:
        clip: ClipHit object to verify
        
    Returns:
        True if clip passes verification, False otherwise
    """
    logger.info(f"Verifying clip {clip.id} with {len(clip.frames)} frames")
    
    try:
        # Skip verification if no frames
        if not clip.frames:
            logger.warning(f"Clip {clip.id} has no frames")
            return False
        
        # Use grid search for initial ranking/verification
        grid_input = GridSearchInput(
            frame_urls=clip.frames[:6],  # Limit to 6 frames for grid
            query=f"Find the most relevant frames for the search query",
            grid_dimensions=(2, 3)
        )
        
        grid_result_str = grid_search(grid_input.json())
        grid_result = robust_json_parse(grid_result_str)
        
        if "error" in grid_result:
            logger.warning(f"Grid search failed for clip {clip.id}: {grid_result['error']}")
            return False
        
        # Check if we can create a video clip for verification
        if clip.video_name and clip.start_frame < clip.end_frame:
            try:
                video_input = GetVideoInput(
                    video_name=clip.video_name,
                    start_frame=clip.start_frame,
                    end_frame=min(clip.end_frame, clip.start_frame + 150)  # Limit clip length
                )
                
                video_result_str = get_video(video_input.json())
                video_result = robust_json_parse(video_result_str)
                
                if video_result.get("success"):
                    clip.url = video_result.get("full_url", "")
                    
                    # Use valid_video_query for final verification
                    valid_input = ValidVideoQueryInput(
                        video_clip_url=clip.url,
                        query_sequence=["Check if this video clip is relevant to the search query"]
                    )
                    
                    valid_result_str = valid_video_query(valid_input.json())
                    valid_result = robust_json_parse(valid_result_str)
                    
                    is_match = valid_result.get("is_match", False)
                    confidence = valid_result.get("confidence_score", 0.0)
                    
                    # Update clip score based on verification
                    clip.score = confidence
                    
                    logger.info(f"Clip {clip.id} verification: match={is_match}, confidence={confidence}")
                    return is_match and confidence > 0.3  # Threshold for acceptance
                    
            except Exception as e:
                logger.warning(f"Video verification failed for clip {clip.id}: {str(e)}")
        
        # Fallback: accept if grid search didn't error and clip has reasonable score
        return clip.score > 0.2
        
    except Exception as e:
        logger.error(f"Error verifying clip {clip.id}: {str(e)}")
        return False


def rerank_clips(clips: List[ClipHit]) -> List[ClipHit]:
    """
    Rerank clips based on verification results and additional criteria.
    
    Args:
        clips: List of verified clips
        
    Returns:
        Reranked list of clips
    """
    logger.info(f"Reranking {len(clips)} clips")
    
    if not clips:
        return clips
    
    # Sort by score (highest first)
    reranked = sorted(clips, key=lambda x: x.score, reverse=True)
    
    # Additional reranking logic could be added here:
    # - Diversity scoring
    # - Temporal coherence
    # - Video quality metrics
    
    logger.info(f"Reranking completed, top score: {reranked[0].score if reranked else 0}")
    return reranked


# LangGraph Node Functions - Note: Node functions already defined above


def embed_search_node(state: SearchState) -> SearchState:
    """Node: Perform embedding-based search."""
    logger.info("=== EMBED SEARCH NODE ===")
    
    try:
        query = state.get("preprocessed_query", state["query"])
        modes = state.get("search_modes", ["text"])
        
        hits = embed_search_api(query, modes, k=10)
        state["hits"] = hits
        
        logger.info(f"Found {len(hits)} initial hits")
        
    except Exception as e:
        logger.error(f"Error in embed_search_node: {str(e)}")
        state["error"] = str(e)
        state["hits"] = []
    
    return state


def verify_clips_parallel(state: SearchState, max_concurrency: int = 8) -> SearchState:
    """Node: Verify clips in parallel with configurable concurrency."""
    logger.info("=== VERIFY CLIPS NODE (PARALLEL) ===")
    
    hits = state.get("hits", [])
    if not hits:
        logger.warning("No hits to verify")
        state["verified"] = []
        return state
    
    verified_clips = []
    
    try:
        # Use ThreadPoolExecutor for parallel verification
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            # Submit all verification tasks
            future_to_clip = {executor.submit(verify_clip, clip): clip for clip in hits}
            
            # Collect results as they complete
            for future in as_completed(future_to_clip):
                clip = future_to_clip[future]
                try:
                    is_verified = future.result()
                    if is_verified:
                        verified_clips.append(clip)
                        logger.info(f"Clip {clip.id} verified successfully")
                    else:
                        logger.info(f"Clip {clip.id} failed verification")
                except Exception as e:
                    logger.error(f"Error verifying clip {clip.id}: {str(e)}")
        
        state["verified"] = verified_clips
        logger.info(f"Verified {len(verified_clips)} out of {len(hits)} clips")
        
    except Exception as e:
        logger.error(f"Error in verify_clips_parallel: {str(e)}")
        state["error"] = str(e)
        state["verified"] = []
    
    return state


def aggregate_results_node(state: SearchState) -> SearchState:
    """Node: Aggregate and filter verification results."""
    logger.info("=== AGGREGATE RESULTS NODE ===")
    
    verified_clips = state.get("verified", [])
    
    # Additional filtering/aggregation logic
    if verified_clips:
        # Remove duplicates based on video content
        unique_clips = []
        seen_videos = set()
        
        for clip in verified_clips:
            video_key = f"{clip.video_name}_{clip.start_frame}_{clip.end_frame}"
            if video_key not in seen_videos:
                unique_clips.append(clip)
                seen_videos.add(video_key)
        
        state["verified"] = unique_clips
        logger.info(f"After deduplication: {len(unique_clips)} unique clips")
    
    return state


def rerank_node(state: SearchState) -> SearchState:
    """Node: Rerank the verified clips."""
    logger.info("=== RERANK NODE ===")
    
    try:
        verified_clips = state.get("verified", [])
        if verified_clips:
            reranked = rerank_clips(verified_clips)
            state["reranked"] = reranked
            logger.info(f"Reranked {len(reranked)} clips")
        else:
            state["reranked"] = []
            logger.info("No clips to rerank")
            
    except Exception as e:
        logger.error(f"Error in rerank_node: {str(e)}")
        state["error"] = str(e)
        state["reranked"] = state.get("verified", [])
    
    return state


class LangGraphVideoRetrieval:
    """
    LangGraph-based video retrieval system.
    Replaces the LangChain agent with a structured graph workflow.
    """
    
    def __init__(self, max_concurrency: int = 8):
        """
        Initialize the LangGraph video retrieval system.
        
        Args:
            max_concurrency: Maximum number of parallel verification workers
        """
        self.max_concurrency = max_concurrency
        self.graph = self._build_graph()
    
    def _build_graph(self) -> Any:
        """Build the LangGraph workflow."""
        if not LANGGRAPH_AVAILABLE:
            logger.error("LangGraph is not available. Please install langgraph package.")
            return None
            
        logger.info("Building LangGraph workflow...")
        
        # Create the state graph
        builder = StateGraph(SearchState)
        
        # Add nodes
        builder.add_node("preprocess", preprocess_query_node)
        builder.add_node("embed_search", embed_search_node)
        builder.add_node("verify_clips", lambda state: verify_clips_parallel(state, self.max_concurrency))
        builder.add_node("aggregate", aggregate_results_node)
        builder.add_node("rerank", rerank_node)
        
        # Add edges to define the workflow
        builder.add_edge(START, "preprocess")
        builder.add_edge("preprocess", "embed_search")
        builder.add_edge("embed_search", "verify_clips")
        builder.add_edge("verify_clips", "aggregate")
        builder.add_edge("aggregate", "rerank")
        builder.add_edge("rerank", END)
        
        # Compile the graph
        graph = builder.compile()
        
        logger.info("LangGraph workflow compiled successfully")
        return graph
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        Execute the search workflow for a given query.
        
        Args:
            query: Search query
            
        Returns:
            Dictionary containing search results and metadata
        """
        logger.info(f"Starting LangGraph search for query: {query[:100]}...")
        
        # Check if LangGraph is available
        if not LANGGRAPH_AVAILABLE or self.graph is None:
            logger.warning("LangGraph not available, falling back to sequential execution")
            return self._search_fallback(query)
        
        # Initialize state
        initial_state = SearchState(
            query=query,
            preprocessed_query="",
            search_modes=[],
            hits=[],
            verified=[],
            reranked=[],
            error="",
            intermediate_results={}
        )
        
        try:
            # Execute the graph
            final_state = self.graph.invoke(initial_state)
            
            # Prepare response
            result = {
                "success": not bool(final_state.get("error")),
                "query": query,
                "preprocessed_query": final_state.get("preprocessed_query", ""),
                "search_modes": final_state.get("search_modes", []),
                "total_hits": len(final_state.get("hits", [])),
                "verified_clips": len(final_state.get("verified", [])),
                "final_results": [],
                "error": final_state.get("error", "")
            }
            
            # Format final results
            reranked_clips = final_state.get("reranked", [])
            for clip in reranked_clips[:5]:  # Return top 5 results
                result["final_results"].append({
                    "clip_id": clip.id,
                    "score": clip.score,
                    "video_url": clip.url,
                    "video_name": clip.video_name,
                    "frame_range": f"{clip.start_frame}-{clip.end_frame}",
                    "frames": clip.frames[:3],  # Limit frames in response
                    "metadata": clip.metadata
                })
            
            logger.info(f"Search completed successfully, found {len(result['final_results'])} results")
            return result
            
        except Exception as e:
            logger.error(f"Error executing LangGraph search: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "final_results": []
            }
    
    def _search_fallback(self, query: str) -> Dict[str, Any]:
        """
        Fallback sequential search when LangGraph is not available.
        
        Args:
            query: Search query
            
        Returns:
            Dictionary containing search results and metadata
        """
        logger.info("Executing fallback sequential search")
        
        try:
            # Initialize state
            state = SearchState(
                query=query,
                preprocessed_query="",
                search_modes=[],
                hits=[],
                verified=[],
                reranked=[],
                error="",
                intermediate_results={}
            )
            
            # Execute nodes sequentially
            state = preprocess_query_node(state)
            if state.get("error"):
                raise Exception(state["error"])
            
            state = embed_search_node(state)
            if state.get("error"):
                raise Exception(state["error"])
            
            state = verify_clips_parallel(state, self.max_concurrency)
            if state.get("error"):
                raise Exception(state["error"])
            
            state = aggregate_results_node(state)
            if state.get("error"):
                raise Exception(state["error"])
            
            state = rerank_node(state)
            if state.get("error"):
                raise Exception(state["error"])
            
            # Prepare response
            result = {
                "success": True,
                "query": query,
                "preprocessed_query": state.get("preprocessed_query", ""),
                "search_modes": state.get("search_modes", []),
                "total_hits": len(state.get("hits", [])),
                "verified_clips": len(state.get("verified", [])),
                "final_results": [],
                "error": ""
            }
            
            # Format final results
            reranked_clips = state.get("reranked", [])
            for clip in reranked_clips[:5]:  # Return top 5 results
                result["final_results"].append({
                    "clip_id": clip.id,
                    "score": clip.score,
                    "video_url": clip.url,
                    "video_name": clip.video_name,
                    "frame_range": f"{clip.start_frame}-{clip.end_frame}",
                    "frames": clip.frames[:3],  # Limit frames in response
                    "metadata": clip.metadata
                })
            
            logger.info(f"Fallback search completed successfully, found {len(result['final_results'])} results")
            return result
            
        except Exception as e:
            logger.error(f"Error in fallback search: {str(e)}")
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "final_results": []
            }


# Global instance for use in the application
_langgraph_retrieval = None


def get_langgraph_retrieval(max_concurrency: int = 8) -> LangGraphVideoRetrieval:
    """Get or create the global LangGraph retrieval instance."""
    global _langgraph_retrieval
    
    if _langgraph_retrieval is None:
        _langgraph_retrieval = LangGraphVideoRetrieval(max_concurrency=max_concurrency)
    
    return _langgraph_retrieval
