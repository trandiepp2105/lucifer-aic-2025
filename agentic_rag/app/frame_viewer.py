"""
Enhanced frame viewer components for the monitoring dashboard.
"""
import streamlit as st
import requests
from PIL import Image
import io
import base64
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd
import json
from datetime import datetime

from .config import config


class FrameViewer:
    """Enhanced frame viewer with grid layout and details."""
    
    def __init__(self):
        """Initialize the frame viewer."""
        self.cache = {}
    
    def display_frames_grid(self, frame_urls: List[str], 
                           step_number: int = None,
                           action_name: str = None,
                           max_columns: int = 4) -> None:
        """
        Display frames in a grid layout with enhanced features.
        
        Args:
            frame_urls: List of frame URLs to display
            step_number: Step number for context
            action_name: Name of the action using these frames
            max_columns: Maximum number of columns in the grid
        """
        if not frame_urls:
            st.info("No frames to display")
            return
        
        # Header
        if step_number and action_name:
            st.markdown(f"**🖼️ Frames used in Step {step_number} - {action_name}**")
        else:
            st.markdown(f"**🖼️ Frames ({len(frame_urls)} total)**")
        
        # Grid settings
        num_frames = len(frame_urls)
        cols_per_row = min(max_columns, num_frames)
        rows = (num_frames + cols_per_row - 1) // cols_per_row
        
        # Display frames in grid
        for row in range(rows):
            cols = st.columns(cols_per_row)
            
            for col_idx in range(cols_per_row):
                frame_idx = row * cols_per_row + col_idx
                
                if frame_idx < num_frames:
                    frame_url = frame_urls[frame_idx]
                    
                    with cols[col_idx]:
                        self.display_single_frame(
                            frame_url, 
                            f"Frame {frame_idx + 1}",
                            show_details=True
                        )
    
    def display_single_frame(self, frame_url: str, 
                           caption: str = None,
                           show_details: bool = False,
                           width: int = None) -> None:
        """
        Display a single frame with enhanced features.
        
        Args:
            frame_url: URL of the frame to display
            caption: Caption for the frame
            show_details: Whether to show detailed frame info
            width: Width for the image display
        """
        try:
            # Load image
            image = self.load_image(frame_url)
            
            if image is None:
                st.error(f"Could not load frame: {frame_url}")
                return
            
            # Display image
            st.image(
                image, 
                caption=caption or "Frame",
                width=width,
                use_column_width=True if width is None else False
            )
            
            # Show details if requested
            if show_details:
                with st.expander("Frame Details", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**URL:** `{frame_url}`")
                        if hasattr(image, 'size'):
                            st.markdown(f"**Size:** {image.size[0]} x {image.size[1]}")
                    
                    with col2:
                        if st.button(f"📋 Copy URL", key=f"copy_{hash(frame_url)}"):
                            st.code(frame_url, language="text")
                        
                        if st.button(f"🔍 View Full Size", key=f"full_{hash(frame_url)}"):
                            st.image(image, caption=f"Full Size - {caption}")
                            
        except Exception as e:
            st.error(f"Error displaying frame: {str(e)}")
            st.text(f"Frame URL: {frame_url}")
    
    def load_image(self, frame_url: str) -> Optional[Image.Image]:
        """
        Load image from URL with caching.
        
        Args:
            frame_url: URL of the image to load
            
        Returns:
            PIL Image or None if loading failed
        """
        # Check cache first
        if frame_url in self.cache:
            return self.cache[frame_url]
        
        try:
            if frame_url.startswith('data:image'):
                # Handle base64 encoded images
                header, data = frame_url.split(',', 1)
                image_data = base64.b64decode(data)
                image = Image.open(io.BytesIO(image_data))
            elif frame_url.startswith('http'):
                # Handle HTTP URLs
                response = requests.get(frame_url, timeout=10)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            else:
                # Handle frame paths by constructing proper media server URL
                # Frame paths like "L05_V027/23583.jpg" need to be fetched from media server
                # Use the same URL construction pattern as get_frames function
                full_url = f"{config.MEDIA_API_URL}/{frame_url}"
                response = requests.get(full_url, timeout=10)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            
            # Cache the image
            self.cache[frame_url] = image
            return image
            
        except Exception as e:
            st.error(f"Error loading image from {frame_url}: {str(e)}")
            return None
    
    def create_frame_comparison(self, frame_urls: List[str], 
                              titles: List[str] = None) -> None:
        """
        Create a side-by-side comparison of frames.
        
        Args:
            frame_urls: List of frame URLs to compare
            titles: Optional titles for each frame
        """
        if not frame_urls:
            return
        
        st.markdown("**🔍 Frame Comparison**")
        
        # Limit to 4 frames for comparison
        compare_frames = frame_urls[:4]
        compare_titles = titles[:4] if titles else [f"Frame {i+1}" for i in range(len(compare_frames))]
        
        cols = st.columns(len(compare_frames))
        
        for i, (frame_url, title) in enumerate(zip(compare_frames, compare_titles)):
            with cols[i]:
                self.display_single_frame(frame_url, title, show_details=False, width=200)
    
    def display_frames_timeline(self, frames_by_step: Dict[int, List[str]]) -> None:
        """
        Display frames in a timeline format showing progression through steps.
        
        Args:
            frames_by_step: Dictionary mapping step numbers to frame lists
        """
        st.markdown("**📊 Frames Timeline**")
        
        if not frames_by_step:
            st.info("No frames timeline available")
            return
        
        for step_num in sorted(frames_by_step.keys()):
            frame_urls = frames_by_step[step_num]
            
            if frame_urls:
                with st.expander(f"Step {step_num} - {len(frame_urls)} frames", expanded=False):
                    self.display_frames_grid(frame_urls, step_num)
    
    def export_frames_info(self, frames_data: Dict[str, Any]) -> str:
        """
        Export frames information to JSON format.
        
        Args:
            frames_data: Dictionary containing frame information
            
        Returns:
            JSON string of frames data
        """
        import json
        
        export_data = {
            "timestamp": str(datetime.now()),
            "frames_count": len(frames_data.get("frames", [])),
            "frames_data": frames_data
        }
        
        return json.dumps(export_data, indent=2, ensure_ascii=False)


class FrameAnalyzer:
    """Analyzer for frame content and patterns."""
    
    def __init__(self):
        """Initialize the analyzer."""
        pass
    
    def analyze_frame_usage(self, session_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze frame usage patterns across agent steps.
        
        Args:
            session_steps: List of session steps with frame data
            
        Returns:
            Dictionary containing usage analysis
        """
        analysis = {
            "total_frames_used": 0,
            "unique_frames": set(),
            "frames_per_step": [],
            "most_used_frames": {},
            "tool_frame_usage": {}
        }
        
        for step in session_steps:
            frames_used = step.get("frames_used", [])
            step_frame_count = len(frames_used)
            
            analysis["total_frames_used"] += step_frame_count
            analysis["frames_per_step"].append(step_frame_count)
            analysis["unique_frames"].update(frames_used)
            
            # Track tool usage
            action = step.get("action")
            if action:
                if action not in analysis["tool_frame_usage"]:
                    analysis["tool_frame_usage"][action] = []
                analysis["tool_frame_usage"][action].extend(frames_used)
            
            # Count frame frequency
            for frame in frames_used:
                analysis["most_used_frames"][frame] = analysis["most_used_frames"].get(frame, 0) + 1
        
        # Convert set to list for JSON serialization
        analysis["unique_frames"] = list(analysis["unique_frames"])
        analysis["unique_frames_count"] = len(analysis["unique_frames"])
        
        return analysis
    
    def display_frame_analytics(self, analysis: Dict[str, Any]) -> None:
        """
        Display frame usage analytics.
        
        Args:
            analysis: Frame usage analysis data
        """
        st.markdown("**📈 Frame Usage Analytics**")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Frames Used", analysis["total_frames_used"])
        
        with col2:
            st.metric("Unique Frames", analysis["unique_frames_count"])
        
        with col3:
            avg_frames_per_step = np.mean(analysis["frames_per_step"]) if analysis["frames_per_step"] else 0
            st.metric("Avg Frames/Step", f"{avg_frames_per_step:.1f}")
        
        with col4:
            max_frames_step = max(analysis["frames_per_step"]) if analysis["frames_per_step"] else 0
            st.metric("Max Frames/Step", max_frames_step)
        
        # Frame usage by tool
        if analysis["tool_frame_usage"]:
            st.markdown("**🛠️ Frame Usage by Tool**")
            
            tool_stats = {}
            for tool, frames in analysis["tool_frame_usage"].items():
                tool_stats[tool] = {
                    "frames_count": len(frames),
                    "unique_frames": len(set(frames))
                }
            
            df_tools = pd.DataFrame(tool_stats).T
            st.dataframe(df_tools, use_container_width=True)
        
        # Most used frames
        if analysis["most_used_frames"]:
            st.markdown("**🔥 Most Used Frames**")
            
            # Sort by usage frequency
            sorted_frames = sorted(
                analysis["most_used_frames"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]  # Show top 10
            
            for frame_url, count in sorted_frames:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{frame_url[:50]}..." if len(frame_url) > 50 else frame_url)
                with col2:
                    st.text(f"Used {count} times")


# Global instances
_frame_viewer = None
_frame_analyzer = None


def get_frame_viewer() -> FrameViewer:
    """Get global frame viewer instance."""
    global _frame_viewer
    if _frame_viewer is None:
        _frame_viewer = FrameViewer()
    return _frame_viewer


def get_frame_analyzer() -> FrameAnalyzer:
    """Get global frame analyzer instance."""
    global _frame_analyzer
    if _frame_analyzer is None:
        _frame_analyzer = FrameAnalyzer()
    return _frame_analyzer
