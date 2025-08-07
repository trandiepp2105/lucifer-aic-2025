"""
Custom callback handler for monitoring agent reasoning steps.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

from .monitoring import get_monitor

logger = logging.getLogger(__name__)


class AgentMonitoringCallback(BaseCallbackHandler):
    """Custom callback handler to monitor agent reasoning steps."""
    
    def __init__(self):
        """Initialize the callback handler."""
        super().__init__()
        self.monitor = get_monitor()
        self.current_step = 0
        self.current_thought = None
        self.current_action = None
        self.current_action_input = None
        
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        """Called when the agent takes an action."""
        self.current_step += 1
        self.current_action = action.tool
        
        # Parse action input
        try:
            if isinstance(action.tool_input, str):
                self.current_action_input = json.loads(action.tool_input)
            else:
                self.current_action_input = action.tool_input
        except (json.JSONDecodeError, TypeError):
            self.current_action_input = {"raw_input": str(action.tool_input)}
        
        # Extract thought from log if available
        thought = None
        if hasattr(action, 'log') and action.log:
            # Try to extract thought from log
            log_lines = action.log.split('\n')
            for line in log_lines:
                if line.strip().startswith('Thought:'):
                    thought = line.replace('Thought:', '').strip()
                    break
        
        # Add step to monitor
        self.monitor.add_step(
            step_number=self.current_step,
            thought=thought,
            action=self.current_action,
            action_input=self.current_action_input
        )
        
        logger.info(f"Agent action: {self.current_action} (Step {self.current_step})")
    
    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """Called when a tool finishes running."""
        if self.current_step > 0:
            # Update the last step with observation
            session = self.monitor.get_current_session()
            if session and session.steps:
                last_step = session.steps[-1]
                if last_step.step_number == self.current_step:
                    last_step.observation = output
                    
                    # Try to extract frames from the output if it's JSON
                    try:
                        output_data = json.loads(output)
                        frames = self._extract_frames_from_output(output_data)
                        if frames:
                            last_step.frames_used.extend(frames)
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        logger.info(f"Tool output received for step {self.current_step}")
    
    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
        """Called when a tool encounters an error."""
        if self.current_step > 0:
            session = self.monitor.get_current_session()
            if session and session.steps:
                last_step = session.steps[-1]
                if last_step.step_number == self.current_step:
                    last_step.observation = f"Error: {str(error)}"
        
        logger.error(f"Tool error in step {self.current_step}: {error}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        """Called when the agent finishes."""
        # Add final step if there's a thought in the finish
        if hasattr(finish, 'log') and finish.log:
            self.current_step += 1
            
            # Extract thought from log
            thought = None
            log_lines = finish.log.split('\n')
            for line in log_lines:
                if line.strip().startswith('Thought:'):
                    thought = line.replace('Thought:', '').strip()
                    break
            
            if thought:
                self.monitor.add_step(
                    step_number=self.current_step,
                    thought=thought
                )
        
        logger.info(f"Agent finished after {self.current_step} steps")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        """Called when LLM starts generating."""
        logger.debug("LLM generation started")
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        """Called when LLM finishes generating."""
        logger.debug("LLM generation completed")
    
    def _extract_frames_from_output(self, output_data: Dict[str, Any]) -> List[str]:
        """Extract frame URLs from tool output."""
        frames = []
        
        # Check common output structures
        if 'frames' in output_data:
            if isinstance(output_data['frames'], list):
                frames.extend(output_data['frames'])
        
        if 'results' in output_data:
            results = output_data['results']
            if isinstance(results, list):
                for result in results:
                    if isinstance(result, dict) and 'frames' in result:
                        frames.extend(result['frames'])
        
        # Check for nested frame structures
        if 'data' in output_data and isinstance(output_data['data'], dict):
            frames.extend(self._extract_frames_from_output(output_data['data']))
        
        return frames
