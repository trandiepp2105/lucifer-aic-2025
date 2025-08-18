# Agent Monitoring System Documentation

## Overview / Tổng quan

Hệ thống Agent Monitoring cung cấp giao diện trực quan để theo dõi quá trình reasoning của agent với các tính năng:

### Features / Tính năng
- 📊 **Sessions Overview**: Xem tổng quan tất cả các phiên reasoning
- 🔍 **Session Details**: Chi tiết từng bước reasoning với visualizations
- 🔴 **Live Monitoring**: Theo dõi real-time agent đang hoạt động
- 🛠️ **Tools Reference**: Thông tin chi tiết về các tools
- 🖼️ **Frame Visualization**: Hiển thị frames được sử dụng ở mỗi bước
- 📈 **Analytics**: Phân tích patterns và performance
- 💾 **Export**: Xuất dữ liệu dưới dạng JSON/HTML

## Architecture / Kiến trúc

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Agent Core        │    │   Monitoring        │    │   Streamlit         │
│   (agent_core.py)   │◄──►│   System            │◄──►│   Dashboard         │
│                     │    │   (monitoring.py)   │    │   (streamlit_*.py)  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                          │                          │
           ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   LangGraph State   │    │   Session Storage   │    │   Frame Viewer      │
│   Management        │    │   (temp files)      │    │   (frame_viewer.py) │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Quick Start / Bắt đầu nhanh

### 1. Installation / Cài đặt
```bash
# Dependencies đã có trong requirements.txt:
# - streamlit==1.29.0
# - plotly
# - pandas

pip install -r requirements.txt
```

### 2. Start Monitoring Dashboard / Khởi động dashboard
```bash
# Option 1: Use script
./run_monitoring.sh

# Option 2: Direct streamlit command
streamlit run streamlit_monitoring.py --server.port 8501
```

### 3. Start Agent API / Khởi động API
```bash
# In another terminal
python -m app.main
# hoặc
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Components / Thành phần

### 1. Monitoring System (`app/monitoring.py`)

#### AgentMonitor Class
```python
monitor = get_monitor()

# Start session
session_id = monitor.start_session("Find video of cat playing")

# Add reasoning steps
monitor.add_step(
    step_number=1,
    thought="I need to search for cat videos",
    action="temporal_frame_search_topk",
    action_input={"query": "cat playing"},
    observation="Found 5 candidates"
)

# End session
monitor.end_session(
    final_answer="Found video with 95% confidence",
    success=True
)
```

#### Data Models
- **AgentSession**: Complete reasoning session
- **AgentStep**: Individual reasoning step
- **Tools Info**: Metadata về các tools

### 2. LangGraph State Management

LangGraph automatically manages workflow state and execution tracking:
```python
# Automatically integrated in agent_core.py
self.agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[AgentMonitoringCallback()]
)
```

### 3. Streamlit Dashboard (`streamlit_monitoring.py`)

#### Pages
1. **Sessions Overview**: 
   - List all sessions
   - Summary statistics
   - Success rate analytics
   - Export functionality

2. **Session Details**:
   - Step-by-step timeline
   - Frame visualizations
   - Tool usage analysis
   - Interactive filters

3. **Live Monitoring**:
   - Real-time session tracking
   - Active step monitoring
   - Auto-refresh functionality

4. **Tools Reference**:
   - Tool descriptions (EN/VI)
   - Input/output formats
   - Use cases and examples

### 4. Frame Viewer (`app/frame_viewer.py`)

Enhanced frame visualization:
```python
frame_viewer = get_frame_viewer()

# Display frames in grid
frame_viewer.display_frames_grid(
    frame_urls=["url1", "url2", "url3"],
    step_number=2,
    action_name="grid_search"
)

# Frame analytics
analyzer = get_frame_analyzer()
analysis = analyzer.analyze_frame_usage(session_steps)
analyzer.display_frame_analytics(analysis)
```

## API Endpoints / API Endpoints

### Monitoring Endpoints
```
GET  /monitoring/sessions          # List all sessions
GET  /monitoring/sessions/{id}     # Get session details
GET  /monitoring/current           # Get current active session
POST /monitoring/export/{id}       # Export session (json/html)
```

### Example Usage
```python
import requests

# Get all sessions
response = requests.get("http://localhost:8000/monitoring/sessions")
sessions = response.json()["sessions"]

# Get session details
session_id = sessions[0]["session_id"]
response = requests.get(f"http://localhost:8000/monitoring/sessions/{session_id}")
session_details = response.json()["session"]

# Export session
response = requests.post(f"http://localhost:8000/monitoring/export/{session_id}?format=html")
export_path = response.json()["export_path"]
```

## Features Detail / Chi tiết tính năng

### 1. Real-time Monitoring / Giám sát real-time
- Automatic step capture via callbacks
- Live dashboard updates
- Session progress tracking
- Error detection and logging

### 2. Frame Visualization / Hiển thị frames
- Grid layout with thumbnails
- Click to view full size
- Frame usage analytics
- Tool-specific frame grouping

### 3. Analytics / Phân tích
- Success rate tracking
- Step count distribution
- Frame usage patterns
- Tool performance metrics

### 4. Export / Xuất dữ liệu
- JSON format for programmatic access
- HTML reports for human reading
- Session data preservation
- Frame URLs included

### 5. Multi-language Support / Hỗ trợ đa ngôn ngữ
- English / Tiếng Việt interface
- Tool descriptions in both languages
- Localized error messages
- Cultural formatting

## Configuration / Cấu hình

### Environment Variables
```bash
# .env file
GOOGLE_API_KEY=your_gemini_api_key
SEARCH_API_URL=your_search_api_url
MEDIA_API_URL=your_media_api_url
DEBUG=true
```

### Streamlit Configuration
```toml
# .streamlit/config.toml
[server]
port = 8501
address = "0.0.0.0"
headless = true

[browser]
gatherUsageStats = false
```

## Troubleshooting / Xử lý sự cố

### Common Issues / Vấn đề thường gặp

1. **Dashboard không hiển thị sessions**
   ```bash
   # Check if agent is running
   curl http://localhost:8000/monitoring/sessions
   
   # Check storage directory
   ls /tmp/agent_sessions/
   ```

2. **Frames không load được**
   - Kiểm tra URL frames có accessible không
   - Verify network connectivity
   - Check image format support

3. **Export không hoạt động**
   - Check write permissions
   - Verify session exists
   - Check disk space

### Debug Mode / Chế độ debug
```bash
# Enable debug logging
export DEBUG=true

# Run with verbose output
streamlit run streamlit_monitoring.py --logger.level=debug
```

## Best Practices / Thực hành tốt

### 1. Performance / Hiệu suất
- Limit frame display count for large sessions
- Use pagination for session lists
- Cache frequently accessed images
- Implement session cleanup

### 2. User Experience / Trải nghiệm người dùng
- Provide clear step descriptions
- Show loading indicators
- Handle errors gracefully
- Offer export options

### 3. Development / Phát triển
- Log all important events
- Validate input parameters
- Handle edge cases
- Test with various session types

## Extensions / Mở rộng

### Custom Tools Integration
```python
# Add custom tool info
tools_info = {
    "custom_tool": {
        "name": "Custom Tool",
        "description_en": "Custom tool description",
        "description_vi": "Mô tả công cụ tùy chỉnh",
        "input_params": ["param1", "param2"],
        "output_format": "Custom output format",
        "use_cases": ["Use case 1", "Use case 2"]
    }
}
```

### Custom Analytics
```python
# Extend frame analyzer
class CustomFrameAnalyzer(FrameAnalyzer):
    def custom_analysis(self, session_steps):
        # Custom analysis logic
        return analysis_results
```

## Support / Hỗ trợ

### Documentation
- Code comments in both English and Vietnamese
- Inline help in dashboard
- Tool descriptions and examples

### Monitoring
- Session storage in temp directory
- Error logging to console
- Performance metrics tracking

---

## Quick Reference / Tham khảo nhanh

### Start Monitoring
```bash
./run_monitoring.sh  # Dashboard on :8501
python -m app.main   # API on :8000
```

### Key URLs
- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs
- Sessions: http://localhost:8000/monitoring/sessions

### Key Files
- `app/monitoring.py` - Core monitoring system
- `streamlit_monitoring.py` - Dashboard interface  
- `app/langgraph_agent.py` - LangGraph workflow integration
- `app/frame_viewer.py` - Frame visualization
