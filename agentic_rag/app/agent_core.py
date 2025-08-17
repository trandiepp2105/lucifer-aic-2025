"""
Agent core functionality using LangGraph for orchestrating the video retrieval process.
This module has been refactored to use LangGraph instead of LangChain for better workflow management.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .config import config
from .schemas import AgentResult, VideoSearchResponse, ErrorResponse
from .monitoring import get_monitor
from .langgraph_agent import get_langgraph_agent, LangGraphVideoAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoRetrievalAgent:
    """
    Main agent class that orchestrates the video retrieval process using LangGraph.
    """
    
    def __init__(self):
        """Initialize the agent with LangGraph workflow."""
        self.monitor = get_monitor()
        self.langgraph_agent = None
        self._setup_agent()
    
    def _setup_agent(self):
        """Setup the LangGraph agent."""
        try:
            # Initialize LangGraph-based agent
            self.langgraph_agent = get_langgraph_agent()
            logger.info("LangGraph agent setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up LangGraph agent: {str(e)}")
            raise

    def find_video(self, descriptions: List[str]) -> Dict[str, Any]:
        """
        Find video clips matching the given descriptions using LangGraph workflow.
        
        Args:
            descriptions: List of natural language descriptions
            
        Returns:
            Dictionary with search results
        """
        try:
            logger.info(f"Starting video search with descriptions: {descriptions}")
            
            # Use LangGraph agent to find video
            result = self.langgraph_agent.find_video(descriptions)
            
            logger.info(f"Video search completed with success: {result.get('success', False)}")
            return result
            
        except Exception as e:
            logger.error(f"Error in find_video: {str(e)}")
            return {
                "success": False,
                "error_type": "system_error",
                "error_message": f"System error: {str(e)}",
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": f"System error occurred: {str(e)}"
            }

    def _handle_parsing_errors(self, error: Exception) -> str:
        """
        Handle parsing errors in workflow execution.
        """
        error_msg = str(error)
        logger.warning(f"Parsing error handled: {error_msg}")
        
        if "JSON" in error_msg or "json" in error_msg:
            return "Please provide a valid JSON response format."
        
        return "Please reformulate your response and try again."
        logger.warning(f"Parsing error detected: {error_msg}")
        
        # Kiểm tra nếu error chứa JSON object được output trực tiếp
        # Global instance for backwards compatibility
_agent_instance = None


def get_agent() -> VideoRetrievalAgent:
    """
    Get the global agent instance (singleton pattern).
    
    Returns:
        VideoRetrievalAgent instance
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = VideoRetrievalAgent()
    return _agent_instance
    
    def _create_system_prompt(self) -> PromptTemplate:
        """Create the system prompt template for the agent."""
        # Tạo các scenarios sử dụng workflow components
        scenarios = {
            "frame_search_with_fallback": AGENT_SCENARIOS["frame_search_with_fallback"].format(
                phase_1=AGENT_WORKFLOW_PHASE_1,
                phase_2=AGENT_WORKFLOW_PHASE_2,
                fallback_strategies=AGENT_FALLBACK_STRATEGIES,
                phase_3=AGENT_WORKFLOW_PHASE_3,
                phase_4=AGENT_WORKFLOW_PHASE_4
            ),
            "question_answering": AGENT_SCENARIOS["question_answering"]
        }
        
        # Tổ hợp tất cả components thành template hoàn chỉnh
        template = f"""{AGENT_CORE_ROLE}

{AGENT_OPERATIONAL_PRINCIPLES}

{AGENT_TEXT_HANDLING}

{AGENT_VALIDATION_STRATEGY}

3. AVAILABLE TOOLS
You have access to the following tools. Use them strictly according to their described functions.

{{tools}}

4. WORKFLOW AND REASONING STRATEGIES

{AGENT_WORKFLOW_PHASE_0}

{scenarios["frame_search_with_fallback"]}

{scenarios["question_answering"]}

{AGENT_MANDATORY_RULES}

{AGENT_GRID_SEARCH_EXAMPLES}

{AGENT_FORMAT_TEMPLATE}"""
                        
        return PromptTemplate(
            template=template,
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"]
        )
    
    def _extract_structured_info_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured information from natural language agent response.
        
        Args:
            text: The natural language response from the agent
            
        Returns:
            Dict containing extracted structured information
        """
        import re
        
        try:
            # Initialize result structure
            result = {
                "success": False,
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": ""
            }
            
            # Look for success indicators
            success_keywords = [
                "successfully match", "frames match", "found frames", "confirmed",
                "validation confirmed", "grid_search validation", "match the description"
            ]
            
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in success_keywords):
                result["success"] = True
            
            # Extract frame URLs using pattern matching
            frame_patterns = [
                r'L\d+_V\d+/\d+\.jpg',  # Pattern like L05_V027/23198.jpg
                r'frame[_\s]*urls?[:\s]*([^\n]+)',  # Look for frame urls
                r'matching[_\s]*frames?[:\s]*([^\n]+)'  # Look for matching frames
            ]
            
            frames = []
            for pattern in frame_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, str):
                        # Extract individual frame URLs from the match
                        frame_urls = re.findall(r'L\d+_V\d+/\d+\.jpg', match)
                        frames.extend(frame_urls)
            
            # Remove duplicates while preserving order
            seen = set()
            result["frames"] = [f for f in frames if not (f in seen or seen.add(f))]
            
            # Extract confidence score
            confidence_patterns = [
                r'confidence[_\s]*score[:\s]*(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*confidence',
                r'score[:\s]*(\d+\.?\d*)'
            ]
            
            for pattern in confidence_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    try:
                        score = float(matches[0])
                        if score > 1.0:
                            score = score / 100.0  # Convert percentage
                        result["confidence_score"] = min(1.0, max(0.0, score))
                        break
                    except ValueError:
                        continue
            
            # If no confidence score found but frames were found, use default
            if result["frames"] and result["confidence_score"] == 0.0:
                result["confidence_score"] = 0.7  # Default reasonable confidence
            
            # Extract reasoning (use the full text as reasoning, cleaned up)
            reasoning_lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line and not line.startswith('**') and not line.startswith('#'):
                    reasoning_lines.append(line)
            
            result["reasoning"] = ' '.join(reasoning_lines[:5])  # Limit to first 5 lines
            
            # Final validation - must have frames for success
            if result["success"] and not result["frames"]:
                result["success"] = False
                result["reasoning"] = "No frame URLs could be extracted from the response"
            
            logger.info(f"Extracted structured info: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting structured info: {e}")
            return {
                "success": False,
                "frames": [],
                "confidence_score": 0.0,
                "reasoning": f"Error parsing response: {str(e)}"
            }
    
    def find_video(self, descriptions: List[str]) -> Dict[str, Any]:
        """
        Main method to find video based on description.
        
        Args:
            description (str): User's description of the desired video
            
        Returns:
            Dict[str, Any]: Result containing video info or error
        """
        try:
            logger.info(f"Starting video search for: {descriptions}")
            
            # Start monitoring session
            query_str = " | ".join(descriptions) if isinstance(descriptions, list) else str(descriptions)
            session_id = self.monitor.start_session(query_str)
            
            try:
                # Execute agent
                result = self.agent_executor.invoke({
                    "input": f"Find video matching description: {descriptions}"
                })
                
                # Parse agent output
                agent_output = result.get("output", "")
                intermediate_steps = result.get("intermediate_steps", [])
                
                logger.info(f"Agent output: {agent_output}")
                
                # Try to extract JSON from agent output (could be in Final Answer or direct output)
                try:
                    # Look for JSON in the output - first try to find complete JSON
                    json_str = None
                    
                    # Check if output contains Final Answer format
                    if "Final Answer:" in agent_output:
                        # Extract everything after "Final Answer:"
                        final_answer_start = agent_output.find("Final Answer:") + len("Final Answer:")
                        final_answer_content = agent_output[final_answer_start:].strip()
                        
                        # Look for JSON in final answer
                        start_idx = final_answer_content.find('{')
                        end_idx = final_answer_content.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            json_str = final_answer_content[start_idx:end_idx]
                    else:
                        # Look for JSON anywhere in the output
                        start_idx = agent_output.find('{')
                        end_idx = agent_output.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            json_str = agent_output[start_idx:end_idx]
                    
                    if json_str:
                        parsed_result = json.loads(json_str)
                        
                        if parsed_result.get("success", False):
                            # End session successfully
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=True
                            )
                            
                            # Adapt to VideoSearchResponse: frames, confidence_score, reasoning
                            return {
                                "success": True,
                                "frames": parsed_result.get("frames", []),
                                "confidence_score": parsed_result.get("confidence_score", 0.0),
                                "reasoning": parsed_result.get("reasoning", "")
                            }
                        else:
                            # End session with failure
                            error_msg = parsed_result.get("error", "No suitable video found")
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=False,
                                error_message=error_msg
                            )
                            
                            return {
                                "success": False,
                                "error_type": "no_match",
                                "error_message": error_msg
                            }
                    else:
                        # If no JSON found, try to extract structured information from the text
                        logger.warning("No JSON found in agent output, attempting to extract structured information")
                        parsed_result = self._extract_structured_info_from_text(agent_output)
                        
                        if parsed_result.get("success", False):
                            # End session successfully
                            json_str = json.dumps(parsed_result)
                            self.monitor.end_session(
                                final_answer=json_str,
                                success=True
                            )
                            
                            return {
                                "success": True,
                                "frames": parsed_result.get("frames", []),
                                "confidence_score": parsed_result.get("confidence_score", 0.0),
                                "reasoning": parsed_result.get("reasoning", "")
                            }
                        else:
                            # End session with failure
                            error_msg = f"Agent did not return a valid result: {agent_output}"
                            self.monitor.end_session(
                                final_answer=agent_output,
                                success=False,
                                error_message=error_msg
                            )
                            
                            return {
                                "success": False,
                                "error_type": "agent_error",
                                "error_message": error_msg
                            }
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing agent output as JSON: {e}")
                    error_msg = f"Error parsing agent result: {str(e)}"
                    self.monitor.end_session(
                        final_answer=agent_output,
                        success=False,
                        error_message=error_msg
                    )
                    
                    return {
                        "success": False,
                        "error_type": "parsing_error",
                        "error_message": error_msg
                    }
                    
            except Exception as e:
                # End session with error
                error_msg = f"Agent execution error: {str(e)}"
                self.monitor.end_session(
                    success=False,
                    error_message=error_msg
                )
                raise
                
        except Exception as e:
            logger.error(f"Error in find_video: {str(e)}")
            return {
                "success": False,
                "error_type": "system_error",
                "error_message": f"System error: {str(e)}"
            }


# Global agent instance
_agent_instance = None


def get_agent() -> VideoRetrievalAgent:
    """
    Get or create the global agent instance.
    
    Returns:
        VideoRetrievalAgent: The agent instance
    """
    global _agent_instance
    
    if _agent_instance is None:
        # Validate configuration first
        config.validate_config()
        _agent_instance = VideoRetrievalAgent()
    
    return _agent_instance


def reset_agent():
    """Reset the global agent instance (useful for testing)."""
    global _agent_instance
    _agent_instance = None
