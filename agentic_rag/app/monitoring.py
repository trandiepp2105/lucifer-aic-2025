"""
Agent monitoring system for tracking and visualizing agent reasoning steps.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import pickle
import tempfile
import os

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """Represents a single reasoning step in agent execution."""
    step_number: int
    timestamp: str
    question: Optional[str] = None
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    frames_used: Optional[List[str]] = None
    tool_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentSession:
    """Represents a complete agent reasoning session."""
    session_id: str
    start_time: str
    end_time: Optional[str]
    query: str
    steps: List[AgentStep]
    final_answer: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'steps': [step.to_dict() for step in self.steps]
        }


class AgentMonitor:
    """
    Agent monitoring system that captures and stores reasoning steps.
    """
    
    def __init__(self):
        """Initialize the monitor."""
        self.current_session: Optional[AgentSession] = None
        self.sessions_storage = self._init_storage()
        self.tools_info = self._load_tools_info()
    
    def _init_storage(self) -> Path:
        """Initialize storage directory for sessions."""
        storage_dir = Path(tempfile.gettempdir()) / "agent_sessions"
        storage_dir.mkdir(exist_ok=True)
        return storage_dir
    
    def _load_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """Load information about available tools."""
        return {
            "temporal_frame_search_topk": {
                "name": "Temporal Frame Search",
                "description_en": "Searches for frame sequences that match temporal event descriptions with text and OCR support",
                "description_vi": "Tìm kiếm chuỗi frame phù hợp với mô tả sự kiện theo thời gian với hỗ trợ text và OCR",
                "input_params": ["query_sequence", "k", "weights"],
                "output_format": "JSON with 'results' containing sequence_score and frames",
                "use_cases": ["Temporal sequences", "Multi-step events", "Text and OCR search"]
            },
            "grid_search": {
                "name": "Grid Search",
                "description_en": "Creates a grid image from multiple frames for simultaneous analysis and comparison",
                "description_vi": "Tạo lưới ảnh từ nhiều frame để phân tích và so sánh đồng thời",
                "input_params": ["frame_urls", "grid_dimensions", "query"],
                "output_format": "JSON with is_match, confidence_score, reasoning",
                "use_cases": ["Batch frame analysis", "Frame comparison", "Quick filtering"]
            },
            "valid_frame_query": {
                "name": "Valid Frame Query",
                "description_en": "Validates whether frame sequences match corresponding descriptions frame-by-frame",
                "description_vi": "Kiểm tra xem chuỗi frame có khớp với mô tả tương ứng từng frame",
                "input_params": ["frames", "queries"],
                "output_format": "JSON with overall_match, confidence_score, reasoning, details",
                "use_cases": ["Detailed validation", "Frame-by-frame checking", "High accuracy needs"]
            }
        }
    
    def start_session(self, query: str) -> str:
        """
        Start a new monitoring session.
        
        Args:
            query: The user's query
            
        Returns:
            str: Session ID
        """
        session_id = str(uuid.uuid4())
        self.current_session = AgentSession(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            end_time=None,
            query=query,
            steps=[],
            metadata={}
        )
        
        logger.info(f"Started monitoring session: {session_id}")
        return session_id
    
    def add_step(self, 
                 step_number: int,
                 question: Optional[str] = None,
                 thought: Optional[str] = None,
                 action: Optional[str] = None,
                 action_input: Optional[Dict[str, Any]] = None,
                 observation: Optional[str] = None,
                 frames_used: Optional[List[str]] = None) -> None:
        """
        Add a reasoning step to the current session.
        
        Args:
            step_number: The step number in the reasoning sequence
            question: The question being asked
            thought: The agent's reasoning/thought
            action: The action/tool being used
            action_input: Input parameters for the action
            observation: The result/observation from the action
            frames_used: List of frame URLs used in this step
        """
        if not self.current_session:
            logger.warning("No active session. Starting new session.")
            self.start_session("Unknown query")
        
        # Extract frames from action_input if present
        if frames_used is None and action_input:
            frames_used = self._extract_frames_from_input(action_input)
        
        # Get tool info
        tool_info = None
        if action:
            tool_info = self.tools_info.get(action, {})
        
        step = AgentStep(
            step_number=step_number,
            timestamp=datetime.now().isoformat(),
            question=question,
            thought=thought,
            action=action,
            action_input=action_input,
            observation=observation,
            frames_used=frames_used or [],
            tool_info=tool_info
        )
        
        self.current_session.steps.append(step)
        logger.info(f"Added step {step_number} to session {self.current_session.session_id}")
    
    def _extract_frames_from_input(self, action_input: Dict[str, Any]) -> List[str]:
        """Extract frame URLs from action input."""
        frames = []
        
        if not action_input:
            return frames
        
        # Check common parameter names that might contain frames
        frame_params = ['frame_urls', 'frames', 'frame_list', 'images']
        for param in frame_params:
            if param in action_input and isinstance(action_input[param], list):
                frames.extend(action_input[param])
        
        # Check for nested structures
        if 'query_sequence' in action_input:
            for item in action_input['query_sequence']:
                if isinstance(item, dict) and 'frames' in item:
                    frames.extend(item['frames'])
        
        return frames
    
    def end_session(self, 
                   final_answer: Optional[str] = None,
                   success: bool = True,
                   error_message: Optional[str] = None) -> None:
        """
        End the current monitoring session.
        
        Args:
            final_answer: The final answer from the agent
            success: Whether the session was successful
            error_message: Error message if any
        """
        if not self.current_session:
            logger.warning("No active session to end.")
            return
        
        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.final_answer = final_answer
        self.current_session.success = success
        self.current_session.error_message = error_message
        
        # Save session
        self._save_session(self.current_session)
        
        logger.info(f"Ended session {self.current_session.session_id}")
        self.current_session = None
    
    def _save_session(self, session: AgentSession) -> None:
        """Save session to storage."""
        try:
            session_file = self.sessions_storage / f"{session.session_id}.pkl"
            with open(session_file, 'wb') as f:
                pickle.dump(session, f)
            
            # Also save as JSON for easy reading
            json_file = self.sessions_storage / f"{session.session_id}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving session: {e}")
    
    def load_session(self, session_id: str) -> Optional[AgentSession]:
        """Load a session from storage."""
        try:
            session_file = self.sessions_storage / f"{session_id}.pkl"
            if session_file.exists():
                with open(session_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
        return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions."""
        sessions = []
        try:
            for session_file in self.sessions_storage.glob("*.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                        sessions.append({
                            'session_id': session_data['session_id'],
                            'start_time': session_data['start_time'],
                            'end_time': session_data.get('end_time'),
                            'query': session_data['query'],
                            'success': session_data.get('success', False),
                            'steps_count': len(session_data.get('steps', []))
                        })
                except Exception as e:
                    logger.error(f"Error reading session file {session_file}: {e}")
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
        
        # Sort by start time, newest first
        sessions.sort(key=lambda x: x['start_time'], reverse=True)
        return sessions
    
    def export_session(self, session_id: str, format: str = 'json') -> Optional[str]:
        """
        Export a session to specified format.
        
        Args:
            session_id: Session ID to export
            format: Export format ('json', 'html')
            
        Returns:
            str: Path to exported file or None if error
        """
        session = self.load_session(session_id)
        if not session:
            return None
        
        try:
            if format == 'json':
                export_file = self.sessions_storage / f"export_{session_id}.json"
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
                return str(export_file)
            
            elif format == 'html':
                export_file = self.sessions_storage / f"export_{session_id}.html"
                html_content = self._generate_html_report(session)
                with open(export_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return str(export_file)
                
        except Exception as e:
            logger.error(f"Error exporting session {session_id}: {e}")
        
        return None
    
    def _generate_html_report(self, session: AgentSession) -> str:
        """Generate HTML report for a session."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Agent Reasoning Report - {session.session_id}</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .step {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .step-header {{ font-weight: bold; color: #333; }}
                .thought {{ background-color: #e8f4fd; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                .action {{ background-color: #fff3cd; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                .observation {{ background-color: #d1ecf1; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                .frames {{ background-color: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                .tool-info {{ background-color: #e2e3e5; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                pre {{ white-space: pre-wrap; word-wrap: break-word; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Agent Reasoning Report</h1>
                <p><strong>Session ID:</strong> {session.session_id}</p>
                <p><strong>Query:</strong> {session.query}</p>
                <p><strong>Start Time:</strong> {session.start_time}</p>
                <p><strong>End Time:</strong> {session.end_time or 'N/A'}</p>
                <p><strong>Success:</strong> {session.success}</p>
                {f'<p><strong>Error:</strong> {session.error_message}</p>' if session.error_message else ''}
                {f'<p><strong>Final Answer:</strong> {session.final_answer}</p>' if session.final_answer else ''}
            </div>
        """
        
        for step in session.steps:
            html += f"""
            <div class="step">
                <div class="step-header">Step {step.step_number} - {step.timestamp}</div>
                {f'<div class="thought"><strong>Thought:</strong><br><pre>{step.thought}</pre></div>' if step.thought else ''}
                {f'<div class="action"><strong>Action:</strong> {step.action}</div>' if step.action else ''}
                {f'<div class="action"><strong>Action Input:</strong><br><pre>{json.dumps(step.action_input, indent=2, ensure_ascii=False)}</pre></div>' if step.action_input else ''}
                {f'<div class="observation"><strong>Observation:</strong><br><pre>{step.observation}</pre></div>' if step.observation else ''}
                {f'<div class="frames"><strong>Frames Used:</strong><br>{", ".join(step.frames_used)}</div>' if step.frames_used else ''}
                {f'<div class="tool-info"><strong>Tool Info:</strong><br><pre>{json.dumps(step.tool_info, indent=2, ensure_ascii=False)}</pre></div>' if step.tool_info else ''}
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        return html
    
    def get_current_session(self) -> Optional[AgentSession]:
        """Get the current active session."""
        return self.current_session


# Global monitor instance
_monitor_instance = None


def get_monitor() -> AgentMonitor:
    """Get or create the global monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = AgentMonitor()
    return _monitor_instance


def reset_monitor():
    """Reset the global monitor instance."""
    global _monitor_instance
    _monitor_instance = None
