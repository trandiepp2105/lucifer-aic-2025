"""
Simplified video retrieval pipeline.
Implements streamlined video search with validation and retry logic.
"""
import logging
import re
from typing import List, Dict, Any, TypedDict, Union, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

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

from .tools import temporal_frame_search_topk, valid_video_query, get_video
from .schemas import TemporalSearchInput, ValidVideoQueryInput, GetVideoInput
from .utils import robust_json_parse, strip_markdown_code_fences
from .config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchState(TypedDict):
    """State definition for the simplified video search workflow."""
    query: str
    descriptions: List[str]  # Original user descriptions
    preprocessed_query: str
    search_modes: List[str]  # e.g., ["text", "ocr", "image"]
    current_attempt: int
    max_attempts: int
    hits: List['ClipHit']
    verified_clips: List['ClipHit']
    final_results: List[Dict[str, Any]]
    user_feedback: Optional[str]
    success: bool
    error_message: Optional[str]
    intermediate_results: Dict[str, Any]


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


def preprocess_query_node(state: SearchState) -> SearchState:
    """
    Node: Preprocess the input query to improve search quality.
    """
    try:
        descriptions = state.get("descriptions", [])
        if not descriptions:
            return {
                **state,
                "success": False,
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
            "current_attempt": state.get("current_attempt", 1),
            "max_attempts": state.get("max_attempts", 3),
            "intermediate_results": {"preprocessing": {"original_length": len(combined_query), "processed_length": len(processed)}}
        }
        
    except Exception as e:
        logger.error(f"Error in preprocess_query_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_message": f"Query preprocessing failed: {str(e)}"
        }


def search_node(state: SearchState) -> SearchState:
    """
    Node: Perform temporal search to find video candidates.
    """
    try:
        preprocessed_query = state.get("preprocessed_query", "")
        if not preprocessed_query:
            return {
                **state,
                "success": False,
                "error_message": "No preprocessed query available"
            }
        
        logger.info(f"Performing search attempt {state.get('current_attempt', 1)}...")
        
        # Prepare temporal search input
        query_sequence = [{"text": preprocessed_query}]
        search_input = TemporalSearchInput(
            query_sequence=query_sequence,
            k=15,  # Get more candidates for validation
            weights={"text": 1.0, "ocr": 0.8}
        )
        
        # Call temporal search tool
        search_result = temporal_frame_search_topk(search_input.model_dump_json())
        result_data = robust_json_parse(search_result)
        
        if "error" in result_data:
            return {
                **state,
                "success": False,
                "error_message": result_data["error"]
            }
        
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
                    first_frame = frames[0]
                    if "_frame_" in first_frame:
                        parts = first_frame.split("_frame_")
                        if len(parts) >= 2:
                            video_name = parts[0].split("/")[-1]
                            try:
                                start_frame = int(parts[1].split(".")[0])
                                end_frame = start_frame + len(frames)
                            except:
                                pass
                
                hit = ClipHit(
                    id=f"hit_{i}",
                    score=score,
                    url="",
                    video_name=video_name,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    frames=frames,
                    metadata=result
                )
                hits.append(hit)
        
        logger.info(f"Found {len(hits)} search hits")
        
        return {
            **state,
            "hits": hits,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "search": {"candidates_found": len(hits)}
            }
        }
        
    except Exception as e:
        logger.error(f"Error in search_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_message": f"Search failed: {str(e)}"
        }


def validate_clips_node(state: SearchState) -> SearchState:
    """
    Node: Validate top 5-10 clips in parallel.
    """
    try:
        hits = state.get("hits", [])
        if not hits:
            return {
                **state,
                "success": False,
                "error_message": "No hits to validate"
            }
        
        # Take top 8 hits for validation
        top_hits = sorted(hits, key=lambda x: x.score, reverse=True)[:8]
        logger.info(f"Validating top {len(top_hits)} clips...")
        
        verified_clips = []
        
        # Validate clips in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_clip = {
                executor.submit(validate_single_clip, clip, state.get("preprocessed_query", "")): clip 
                for clip in top_hits
            }
            
            for future in as_completed(future_to_clip):
                clip = future_to_clip[future]
                try:
                    is_valid, confidence = future.result()
                    if is_valid:
                        clip.score = confidence  # Update score with validation result
                        verified_clips.append(clip)
                        logger.info(f"Clip {clip.id} validated with confidence {confidence:.2f}")
                except Exception as e:
                    logger.error(f"Error validating clip {clip.id}: {str(e)}")
        
        logger.info(f"Validated {len(verified_clips)} out of {len(top_hits)} clips")
        
        return {
            **state,
            "verified_clips": verified_clips,
            "intermediate_results": {
                **state.get("intermediate_results", {}),
                "validation": {
                    "clips_validated": len(top_hits),
                    "clips_passed": len(verified_clips)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in validate_clips_node: {str(e)}")
        return {
            **state,
            "success": False,
            "error_message": f"Validation failed: {str(e)}"
        }


def validate_single_clip(clip: ClipHit, query: str) -> tuple:
    """
    Validate a single clip against the query.
    
    Returns:
        Tuple of (is_valid, confidence_score)
    """
    try:
        if not clip.frames or not clip.video_name:
            return False, 0.0
        
        # Generate video clip if we have the necessary info
        if clip.start_frame < clip.end_frame:
            try:
                video_input = GetVideoInput(
                    video_name=clip.video_name,
                    start_frame=clip.start_frame,
                    end_frame=min(clip.end_frame, clip.start_frame + 150)  # Limit clip length
                )
                
                video_result_str = get_video(video_input.model_dump_json())
                video_result = robust_json_parse(video_result_str)
                
                if video_result.get("success"):
                    clip.url = video_result.get("clip_url", "")
                    
                    # Validate the video clip
                    validation_input = ValidVideoQueryInput(
                        video_clip_url=clip.url,
                        query_sequence=[{"text": query}],
                        question=f"Does this video clip match the description: {query}?"
                    )
                    
                    valid_result_str = valid_video_query(validation_input.model_dump_json())
                    valid_result = robust_json_parse(valid_result_str)
                    
                    is_match = valid_result.get("is_match", False)
                    confidence = valid_result.get("confidence_score", 0.0)
                    
                    # Threshold for acceptance
                    return is_match and confidence > 0.4, confidence
                    
            except Exception as e:
                logger.warning(f"Video validation failed for clip {clip.id}: {str(e)}")
        
        # Fallback: accept if clip has reasonable score
        return clip.score > 0.3, clip.score
        
    except Exception as e:
        logger.error(f"Error validating clip {clip.id}: {str(e)}")
        return False, 0.0


def decision_node(state: SearchState) -> SearchState:
    """
    Node: Decide if we have good results or need to retry.
    """
    verified_clips = state.get("verified_clips", [])
    current_attempt = state.get("current_attempt", 1)
    max_attempts = state.get("max_attempts", 3)
    
    # Sort verified clips by score
    verified_clips.sort(key=lambda x: x.score, reverse=True)
    
    # If we have good results (at least 2 clips with confidence > 0.6)
    good_clips = [clip for clip in verified_clips if clip.score > 0.6]
    
    if len(good_clips) >= 2:
        logger.info(f"Found {len(good_clips)} high-confidence clips, finishing search")
        final_results = []
        for clip in verified_clips[:5]:  # Return top 5
            final_results.append({
                "video_name": clip.video_name,
                "start_frame": clip.start_frame,
                "end_frame": clip.end_frame,
                "frames": clip.frames[:5],  # Limit frames returned
                "confidence_score": clip.score,
                "clip_url": clip.url
            })
        
        return {
            **state,
            "success": True,
            "final_results": final_results,
            "verified_clips": verified_clips
        }
    
    # If we have some results but not great, and haven't maxed out attempts
    elif len(verified_clips) > 0 and current_attempt < max_attempts:
        logger.info(f"Found {len(verified_clips)} clips but quality not great, will retry with refined query")
        return {
            **state,
            "success": False,
            "error_message": f"Results quality insufficient (attempt {current_attempt}/{max_attempts}), preparing retry",
            "verified_clips": verified_clips
        }
    
    # No attempts left or no results
    else:
        if verified_clips:
            # Return what we have
            final_results = []
            for clip in verified_clips[:3]:
                final_results.append({
                    "video_name": clip.video_name,
                    "start_frame": clip.start_frame,
                    "end_frame": clip.end_frame,
                    "frames": clip.frames[:5],
                    "confidence_score": clip.score,
                    "clip_url": clip.url
                })
            
            return {
                **state,
                "success": True,
                "final_results": final_results,
                "verified_clips": verified_clips,
                "error_message": f"Found {len(verified_clips)} candidates but confidence is lower than ideal"
            }
        else:
            return {
                **state,
                "success": False,
                "final_results": [],
                "error_message": f"No suitable videos found after {current_attempt} attempts"
            }


def retry_node(state: SearchState) -> SearchState:
    """
    Node: Prepare for retry with refined query.
    """
    current_attempt = state.get("current_attempt", 1)
    verified_clips = state.get("verified_clips", [])
    original_query = state.get("preprocessed_query", "")
    
    # Analyze why previous search might have failed
    if verified_clips:
        # We had some results but low confidence - refine the query
        refined_query = f"Looking for videos that clearly show: {original_query}. Must be highly relevant and specific."
    else:
        # No results - try broader search
        refined_query = f"Find any videos related to: {original_query}. Include similar or related content."
    
    logger.info(f"Retrying search (attempt {current_attempt + 1}) with refined query: {refined_query[:100]}...")
    
    return {
        **state,
        "preprocessed_query": refined_query,
        "current_attempt": current_attempt + 1,
        "hits": [],  # Clear previous hits
        "verified_clips": [],  # Clear previous results
        "success": False,
        "error_message": None
    }


def should_retry(state: SearchState) -> str:
    """Conditional edge: Determine if we should retry or finish."""
    if state.get("success"):
        return "finish"
    
    current_attempt = state.get("current_attempt", 1)
    max_attempts = state.get("max_attempts", 3)
    
    if current_attempt < max_attempts:
        return "retry"
    else:
        return "finish"


def finish_node(state: SearchState) -> SearchState:
    """
    Node: Final processing and cleanup.
    """
    final_results = state.get("final_results", [])
    success = state.get("success", False)
    
    logger.info(f"Search finished. Success: {success}, Results: {len(final_results)}")
    
    # Add metadata about the search process
    search_metadata = {
        "total_attempts": state.get("current_attempt", 1),
        "final_success": success,
        "results_count": len(final_results),
        "intermediate_results": state.get("intermediate_results", {})
    }
    
    return {
        **state,
        "search_metadata": search_metadata,
        "final_results": final_results
    }


class SimplifiedVideoRetrieval:
    """
    Simplified video retrieval system with search, validation, and retry logic.
    """
    
    def __init__(self, max_attempts: int = 3):
        """
        Initialize the simplified video retrieval system.
        
        Args:
            max_attempts: Maximum number of search attempts
        """
        self.max_attempts = max_attempts
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph is not available. Will use fallback sequential execution.")
            return None
            
        logger.info("Building simplified LangGraph workflow...")
        
        # Create the state graph
        builder = StateGraph(SearchState)
        
        # Add nodes
        builder.add_node("preprocess", preprocess_query_node)
        builder.add_node("search", search_node)
        builder.add_node("validate", validate_clips_node)
        builder.add_node("decision", decision_node)
        builder.add_node("retry", retry_node)
        builder.add_node("finish", finish_node)
        
        # Add edges to define the workflow
        builder.add_edge(START, "preprocess")
        builder.add_edge("preprocess", "search")
        builder.add_edge("search", "validate")
        builder.add_edge("validate", "decision")
        
        # Add conditional edges
        builder.add_conditional_edges(
            "decision",
            should_retry,
            {
                "retry": "retry",
                "finish": "finish"
            }
        )
        
        builder.add_edge("retry", "search")  # Retry goes back to search
        builder.add_edge("finish", END)
        
        # Compile the graph
        graph = builder.compile()
        
        logger.info("Simplified LangGraph workflow compiled successfully")
        return graph
    
    def search(self, descriptions: List[str], user_feedback: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the search workflow for given descriptions.
        
        Args:
            descriptions: List of natural language descriptions
            user_feedback: Optional user feedback to improve search
            
        Returns:
            Dictionary containing search results and metadata
        """
        logger.info(f"Starting simplified search for descriptions: {descriptions}")
        
        # Initialize state
        initial_state = SearchState(
            query="",
            descriptions=descriptions,
            preprocessed_query="",
            search_modes=[],
            current_attempt=1,
            max_attempts=self.max_attempts,
            hits=[],
            verified_clips=[],
            final_results=[],
            user_feedback=user_feedback,
            success=False,
            error_message=None,
            intermediate_results={}
        )
        
        if not LANGGRAPH_AVAILABLE or self.graph is None:
            logger.warning("LangGraph not available, using fallback sequential execution")
            return self._search_fallback(initial_state)
        
        try:
            # Execute the graph
            final_state = self.graph.invoke(initial_state)
            
            # Prepare response
            result = {
                "success": final_state.get("success", False),
                "descriptions": descriptions,
                "final_results": final_state.get("final_results", []),
                "search_metadata": final_state.get("search_metadata", {}),
                "user_feedback": user_feedback,
                "error_message": final_state.get("error_message")
            }
            
            logger.info(f"Search completed. Success: {result['success']}, Results: {len(result['final_results'])}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing simplified search: {str(e)}")
            return {
                "success": False,
                "descriptions": descriptions,
                "error_message": str(e),
                "final_results": []
            }
    
    def _search_fallback(self, state: SearchState) -> Dict[str, Any]:
        """
        Fallback sequential search when LangGraph is not available.
        """
        logger.info("Executing fallback sequential search")
        
        try:
            # Execute nodes sequentially
            state = preprocess_query_node(state)
            if state.get("error_message"):
                return {"success": False, "error_message": state["error_message"], "final_results": []}
            
            # Retry loop
            while state.get("current_attempt", 1) <= state.get("max_attempts", 3):
                state = search_node(state)
                if state.get("error_message"):
                    break
                
                state = validate_clips_node(state)
                if state.get("error_message"):
                    break
                
                state = decision_node(state)
                
                if state.get("success"):
                    break
                
                # Check if we should retry
                if state.get("current_attempt", 1) < state.get("max_attempts", 3):
                    state = retry_node(state)
                else:
                    break
            
            state = finish_node(state)
            
            return {
                "success": state.get("success", False),
                "descriptions": state.get("descriptions", []),
                "final_results": state.get("final_results", []),
                "search_metadata": state.get("search_metadata", {}),
                "error_message": state.get("error_message")
            }
            
        except Exception as e:
            logger.error(f"Error in fallback search: {str(e)}")
            return {
                "success": False,
                "error_message": str(e),
                "final_results": []
            }
    
    def add_user_feedback(self, feedback: str, previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Incorporate user feedback and re-run search.
        
        Args:
            feedback: User feedback about previous results
            previous_results: Previous search results
            
        Returns:
            New search results incorporating feedback
        """
        logger.info(f"Incorporating user feedback: {feedback[:100]}...")
        
        descriptions = previous_results.get("descriptions", [])
        
        # Modify descriptions based on feedback
        if "not" in feedback.lower() or "wrong" in feedback.lower():
            # User is saying results are wrong - try different approach
            modified_descriptions = [f"NOT {desc}" for desc in descriptions]
            modified_descriptions.append(f"Instead, looking for: {feedback}")
        else:
            # User is providing additional context
            modified_descriptions = descriptions + [f"Additional context: {feedback}"]
        
        return self.search(modified_descriptions, user_feedback=feedback)


# Global instance for use in the application
_simplified_retrieval = None


def get_simplified_retrieval(max_attempts: int = 3) -> SimplifiedVideoRetrieval:
    """Get or create the global simplified retrieval instance."""
    global _simplified_retrieval
    
    if _simplified_retrieval is None:
        _simplified_retrieval = SimplifiedVideoRetrieval(max_attempts=max_attempts)
    
    return _simplified_retrieval
