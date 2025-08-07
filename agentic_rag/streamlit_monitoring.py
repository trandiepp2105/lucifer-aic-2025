"""
Streamlit dashboard for monitoring and visualizing agent reasoning steps.
"""
import streamlit as st
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from PIL import Image
import io
import base64
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# Import monitoring system
from app.monitoring import get_monitor, AgentSession, AgentStep
from app.frame_viewer import get_frame_viewer, get_frame_analyzer


class AgentMonitoringDashboard:
    """Streamlit dashboard for agent monitoring."""
    
    def __init__(self):
        """Initialize the dashboard."""
        self.monitor = get_monitor()
        self.frame_viewer = get_frame_viewer()
        self.frame_analyzer = get_frame_analyzer()
        self.setup_page_config()
    
    def setup_page_config(self):
        """Configure Streamlit page."""
        st.set_page_config(
            page_title="Agent Monitoring Dashboard",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def run(self):
        """Main dashboard interface."""
        st.title("🤖 Agent Reasoning Monitor")
        st.markdown("---")
        
        # Sidebar for navigation
        with st.sidebar:
            st.header("Navigation")
            page = st.selectbox(
                "Choose Page",
                ["Sessions Overview", "Session Details", "Live Monitoring", "Tools Reference"],
                index=0
            )
            
            # Language selection
            st.markdown("---")
            language = st.selectbox("Language / Ngôn ngữ", ["English", "Tiếng Việt"], index=0)
            st.session_state.language = language
        
        # Route to appropriate page
        if page == "Sessions Overview":
            self.sessions_overview_page()
        elif page == "Session Details":
            self.session_details_page()
        elif page == "Live Monitoring":
            self.live_monitoring_page()
        elif page == "Tools Reference":
            self.tools_reference_page()
    
    def sessions_overview_page(self):
        """Sessions overview page."""
        lang = st.session_state.get('language', 'English')
        
        if lang == "Tiếng Việt":
            st.header("📊 Tổng quan các phiên")
            st.markdown("Xem tất cả các phiên reasoning của agent")
        else:
            st.header("📊 Sessions Overview")
            st.markdown("View all agent reasoning sessions")
        
        # Get sessions list
        sessions = self.monitor.list_sessions()
        
        if not sessions:
            if lang == "Tiếng Việt":
                st.info("Chưa có phiên nào được ghi nhận.")
            else:
                st.info("No sessions recorded yet.")
            return
        
        # Display sessions summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Sessions" if lang == "English" else "Tổng số phiên",
                len(sessions)
            )
        
        with col2:
            successful_sessions = sum(1 for s in sessions if s.get('success', False))
            st.metric(
                "Successful" if lang == "English" else "Thành công",
                successful_sessions
            )
        
        with col3:
            failed_sessions = len(sessions) - successful_sessions
            st.metric(
                "Failed" if lang == "English" else "Thất bại",
                failed_sessions
            )
        
        with col4:
            avg_steps = sum(s.get('steps_count', 0) for s in sessions) / len(sessions) if sessions else 0
            st.metric(
                "Avg Steps" if lang == "English" else "TB số bước",
                f"{avg_steps:.1f}"
            )
        
        # Sessions table
        st.markdown("---")
        if lang == "Tiếng Việt":
            st.subheader("📋 Danh sách phiên")
        else:
            st.subheader("📋 Sessions List")
        
        # Convert to DataFrame for better display
        df = pd.DataFrame(sessions)
        if not df.empty:
            df['start_time'] = pd.to_datetime(df['start_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['end_time'] = pd.to_datetime(df['end_time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Session selection
            session_options = []
            for idx, row in df.iterrows():
                option_text = f"{row['session_id']} - {row['start_time']} - {row['query'][:50]}..."
                session_options.append(option_text)
            
            selected_session_text = st.selectbox(
                "Select a session" if lang == "English" else "Chọn phiên",
                options=session_options,
                index=0
            )
            
            # Get selected session index
            selected_idx = session_options.index(selected_session_text) if selected_session_text else 0
            
            # Display dataframe (without selection functionality)
            st.dataframe(
                df[['session_id', 'start_time', 'end_time', 'query', 'success', 'steps_count']],
                use_container_width=True
            )
            
            # Session actions
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("View Details" if lang == "English" else "Xem chi tiết"):
                    st.session_state.selected_session_id = df.iloc[selected_idx]['session_id']
                    st.rerun()
            
            with col2:
                if st.button("Export JSON" if lang == "English" else "Xuất JSON"):
                    session_id = df.iloc[selected_idx]['session_id']
                    export_path = self.monitor.export_session(session_id, 'json')
                    if export_path:
                        st.success(f"Exported to: {export_path}")
                    else:
                        st.error("Export failed")
            
            with col3:
                if st.button("Export HTML" if lang == "English" else "Xuất HTML"):
                    session_id = df.iloc[selected_idx]['session_id']
                    export_path = self.monitor.export_session(session_id, 'html')
                    if export_path:
                        st.success(f"Exported to: {export_path}")
                    else:
                        st.error("Export failed")
        
        # Charts
        if len(sessions) > 1:
            st.markdown("---")
            if lang == "Tiếng Việt":
                st.subheader("📈 Thống kê")
            else:
                st.subheader("📈 Analytics")
            
            self.display_analytics(sessions)
    
    def session_details_page(self):
        """Session details page."""
        lang = st.session_state.get('language', 'English')
        
        if lang == "Tiếng Việt":
            st.header("🔍 Chi tiết phiên")
        else:
            st.header("🔍 Session Details")
        
        # Session selection
        sessions = self.monitor.list_sessions()
        if not sessions:
            if lang == "Tiếng Việt":
                st.info("Chưa có phiên nào để hiển thị.")
            else:
                st.info("No sessions available to display.")
            return
        
        # Session selector
        session_options = {f"{s['session_id'][:8]}... - {s['query'][:50]}...": s['session_id'] for s in sessions}
        
        selected_session_key = st.selectbox(
            "Select Session" if lang == "English" else "Chọn phiên",
            options=list(session_options.keys()),
            index=0
        )
        
        session_id = session_options[selected_session_key]
        
        # Load and display session
        session = self.monitor.load_session(session_id)
        if not session:
            st.error("Could not load session" if lang == "English" else "Không thể tải phiên")
            return
        
        self.display_session_details(session)
    
    def display_session_details(self, session: AgentSession):
        """Display detailed session information."""
        lang = st.session_state.get('language', 'English')
        
        # Session header
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**Session ID:** `{session.session_id}`")
            st.markdown(f"**Query:** {session.query}")
            
        with col2:
            success_color = "🟢" if session.success else "🔴"
            st.markdown(f"**Status:** {success_color} {'Success' if session.success else 'Failed'}")
            st.markdown(f"**Steps:** {len(session.steps)}")
        
        # Timeline visualization
        st.markdown("---")
        if lang == "Tiếng Việt":
            st.subheader("⏱️ Timeline Reasoning")
        else:
            st.subheader("⏱️ Reasoning Timeline")
        
        self.display_reasoning_timeline(session)
        
        # Step-by-step details
        st.markdown("---")
        if lang == "Tiếng Việt":
            st.subheader("📝 Chi tiết từng bước")
        else:
            st.subheader("📝 Step-by-Step Details")
        
        # Frame analytics
        if session.steps:
            steps_data = [step.to_dict() for step in session.steps]
            analysis = self.frame_analyzer.analyze_frame_usage(steps_data)
            
            st.subheader("📊 Frame Usage Analytics")
            with st.container():
                self.frame_analyzer.display_frame_analytics(analysis)
        
        # Step filter
        step_numbers = list(range(1, len(session.steps) + 1))
        selected_steps = st.multiselect(
            "Filter Steps" if lang == "English" else "Lọc bước",
            options=step_numbers,
            default=step_numbers
        )
        
        for step in session.steps:
            if step.step_number in selected_steps:
                self.display_step_details(step)
    
    def display_reasoning_timeline(self, session: AgentSession):
        """Display interactive timeline of reasoning steps."""
        # Create timeline data
        timeline_data = []
        for step in session.steps:
            timeline_data.append({
                'Step': step.step_number,
                'Action': step.action or 'Thinking',
                'Timestamp': step.timestamp,
                'Success': 'Success' if step.observation and 'error' not in step.observation.lower() else 'Issue'
            })
        
        if timeline_data:
            df = pd.DataFrame(timeline_data)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            # Create timeline chart
            fig = px.scatter(
                df, 
                x='Timestamp', 
                y='Step', 
                color='Success',
                hover_data=['Action'],
                title='Reasoning Timeline',
                color_discrete_map={'Success': 'green', 'Issue': 'red'}
            )
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    def display_step_details(self, step: AgentStep):
        """Display details for a single reasoning step."""
        lang = st.session_state.get('language', 'English')
        
        with st.expander(f"Step {step.step_number} - {step.action or 'Thinking'}", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Thought
                if step.thought:
                    st.markdown("**💭 Thought:**")
                    st.text_area(
                        "thought", 
                        step.thought, 
                        height=100, 
                        disabled=True,
                        label_visibility="collapsed"
                    )
                
                # Action and input
                if step.action:
                    st.markdown(f"**🔧 Action:** `{step.action}`")
                    
                    if step.action_input:
                        st.markdown("**📥 Action Input:**")
                        st.json(step.action_input)
                
                # Observation
                if step.observation:
                    st.markdown("**👁️ Observation:**")
                    st.text_area(
                        "observation", 
                        step.observation, 
                        height=150, 
                        disabled=True,
                        label_visibility="collapsed"
                    )
            
            with col2:
                st.markdown(f"**⏰ Timestamp:**")
                st.text(step.timestamp)
                
                # Tool info
                if step.tool_info:
                    st.markdown("**🛠️ Tool Info:**")
                    tool_name = step.tool_info.get('name', 'Unknown')
                    if lang == "Tiếng Việt":
                        description = step.tool_info.get('description_vi', step.tool_info.get('description_en', ''))
                    else:
                        description = step.tool_info.get('description_en', step.tool_info.get('description_vi', ''))
                    
                    st.markdown(f"**{tool_name}**")
                    st.markdown(description)
                
                # Frames used
                if step.frames_used:
                    st.markdown(f"**🖼️ Frames Used:** {len(step.frames_used)}")
                    
                    # Use enhanced frame viewer
                    self.frame_viewer.display_frames_grid(
                        step.frames_used,
                        step_number=step.step_number,
                        action_name=step.action,
                        max_columns=3
                    )
    
    def live_monitoring_page(self):
        """Live monitoring page."""
        lang = st.session_state.get('language', 'English')
        
        if lang == "Tiếng Việt":
            st.header("🔴 Giám sát trực tiếp")
            st.markdown("Theo dõi hoạt động của agent trong thời gian thực")
        else:
            st.header("🔴 Live Monitoring")
            st.markdown("Monitor agent activity in real-time")
        
        # Current session info
        current_session = self.monitor.get_current_session()
        
        if current_session:
            st.success("Active session detected!" if lang == "English" else "Phát hiện phiên đang hoạt động!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Session ID", current_session.session_id[:8] + "...")
            with col2:
                st.metric("Steps", len(current_session.steps))
            with col3:
                duration = datetime.now() - datetime.fromisoformat(current_session.start_time)
                st.metric("Duration", f"{duration.total_seconds():.0f}s")
            
            # Real-time steps display
            if current_session.steps:
                st.markdown("---")
                st.subheader("Latest Steps" if lang == "English" else "Các bước gần nhất")
                
                # Show last 5 steps
                recent_steps = current_session.steps[-5:]
                for step in reversed(recent_steps):
                    with st.container():
                        col1, col2, col3 = st.columns([1, 2, 2])
                        with col1:
                            st.markdown(f"**Step {step.step_number}**")
                        with col2:
                            st.markdown(f"**Action:** {step.action or 'Thinking'}")
                        with col3:
                            st.markdown(f"**Time:** {step.timestamp.split('T')[1][:8]}")
                        
                        if step.thought:
                            st.text(step.thought[:200] + "..." if len(step.thought) > 200 else step.thought)
                        st.markdown("---")
            
            # Auto-refresh
            if st.button("🔄 Refresh" if lang == "English" else "🔄 Làm mới"):
                st.rerun()
        else:
            st.info("No active session" if lang == "English" else "Không có phiên nào đang hoạt động")
            
            if st.button("Check for sessions" if lang == "English" else "Kiểm tra phiên"):
                st.rerun()
    
    def tools_reference_page(self):
        """Tools reference page."""
        lang = st.session_state.get('language', 'English')
        
        if lang == "Tiếng Việt":
            st.header("🛠️ Tham khảo công cụ")
            st.markdown("Thông tin chi tiết về các công cụ mà agent có thể sử dụng")
        else:
            st.header("🛠️ Tools Reference")
            st.markdown("Detailed information about tools available to the agent")
        
        tools_info = self.monitor.tools_info
        
        for tool_id, tool_info in tools_info.items():
            with st.expander(f"🔧 {tool_info['name']}", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("**Description:**")
                    if lang == "Tiếng Việt":
                        description = tool_info.get('description_vi', tool_info.get('description_en', ''))
                    else:
                        description = tool_info.get('description_en', tool_info.get('description_vi', ''))
                    st.markdown(description)
                    
                    st.markdown("**Input Parameters:**")
                    st.code(", ".join(tool_info.get('input_params', [])))
                    
                    st.markdown("**Output Format:**")
                    st.code(tool_info.get('output_format', 'Not specified'))
                
                with col2:
                    st.markdown("**Use Cases:**")
                    use_cases = tool_info.get('use_cases', [])
                    for use_case in use_cases:
                        st.markdown(f"• {use_case}")
    
    def display_analytics(self, sessions: List[Dict[str, Any]]):
        """Display analytics charts."""
        col1, col2 = st.columns(2)
        
        with col1:
            # Success rate over time
            df = pd.DataFrame(sessions)
            df['start_time'] = pd.to_datetime(df['start_time'])
            df['date'] = df['start_time'].dt.date
            
            daily_stats = df.groupby('date').agg({
                'success': ['count', 'sum']
            }).round(2)
            daily_stats.columns = ['total', 'successful']
            daily_stats['success_rate'] = (daily_stats['successful'] / daily_stats['total'] * 100).round(1)
            
            fig = px.line(
                daily_stats.reset_index(), 
                x='date', 
                y='success_rate',
                title='Success Rate Over Time (%)',
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Steps distribution
            steps_data = [s.get('steps_count', 0) for s in sessions]
            fig = px.histogram(
                x=steps_data,
                title='Distribution of Steps per Session',
                nbins=10
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def is_valid_image_url(self, url: str) -> bool:
        """Check if URL is a valid image URL."""
        if not url:
            return False
        
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        return any(url.lower().endswith(ext) for ext in image_extensions) or 'image' in url.lower()


def main():
    """Main function to run the dashboard."""
    dashboard = AgentMonitoringDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
