# Team Answer Real-time Updates with SSE

Hệ thống Server-Sent Events (SSE) cho phép client nhận cập nhật team answer theo thời gian thực mà không cần phải reload hoặc polling.

## 🚀 **Cách hoạt động**

### **Server-Side Events:**
- **Create**: Khi có team answer mới được tạo
- **Delete**: Khi có team answer bị xóa (single hoặc bulk delete)
- **Heartbeat**: Tin nhắn duy trì kết nối
- **Connected**: Xác nhận kết nối thành công

### **Redis Pub/Sub:**
- Sử dụng Redis channel: `team_answers_updates`
- Tất cả instances Django đều có thể publish messages
- Client SSE subscribers nhận messages qua Redis pub/sub

## 📡 **API Endpoints**

### **SSE Endpoint:**
```
GET /api/team-answers/sse/
```
- **Content-Type**: `text/event-stream`
- **Headers**: 
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `Access-Control-Allow-Origin: *`

### **Team Answer Endpoints với SSE:**
```
POST /api/team-answers/          # Tạo mới -> gửi SSE "create"
DELETE /api/team-answers/{id}/   # Xóa 1 -> gửi SSE "delete"
DELETE /api/team-answers/delete-all/  # Xóa nhiều -> gửi SSE "delete"
```

## 📝 **Message Format**

### **Create Message:**
```json
{
  "type": "create",
  "data": {
    "id": 123,
    "video_name": "video.mp4",
    "frame_index": 100,
    "url": "http://example.com/frame.jpg",
    "qa": "Question and answer text",
    "query_index": 1,
    "round": "prelims",
    "created_at": "2025-07-12T10:30:00Z",
    "updated_at": "2025-07-12T10:30:00Z"
  },
  "timestamp": "2025-07-12T10:30:00Z"
}
```

### **Delete Message:**
```json
{
  "type": "delete",
  "data": [123, 124, 125],
  "timestamp": "2025-07-12T10:30:00Z"
}
```

### **Connected Message:**
```json
{
  "type": "connected",
  "message": "Connected to team answers real-time updates",
  "timestamp": "2025-07-12T10:30:00Z"
}
```

### **Heartbeat Message:**
```json
{
  "type": "heartbeat",
  "timestamp": "2025-07-12T10:30:00Z"
}
```

## 💻 **Client Implementation Example**

### **JavaScript (Frontend):**
```javascript
// Kết nối SSE
const eventSource = new EventSource('/api/team-answers/sse/');

// Lắng nghe messages
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'connected':
            console.log('Connected to team answers updates');
            break;
            
        case 'create':
            // Thêm team answer mới vào danh sách
            addTeamAnswerToList(data.data);
            break;
            
        case 'delete':
            // Xóa team answers khỏi danh sách
            removeTeamAnswersFromList(data.data);
            break;
            
        case 'heartbeat':
            // Duy trì kết nối
            console.log('Heartbeat received');
            break;
            
        case 'error':
            console.error('SSE Error:', data.message);
            break;
    }
};

// Xử lý lỗi kết nối
eventSource.onerror = function(event) {
    console.error('SSE connection error:', event);
};

// Đóng kết nối khi cần
function closeSseConnection() {
    eventSource.close();
}

// Functions để cập nhật UI
function addTeamAnswerToList(teamAnswer) {
    // Thêm team answer vào danh sách hiện tại
    // Cập nhật state/DOM
}

function removeTeamAnswersFromList(deletedIds) {
    // Xóa team answers có ID trong deletedIds
    // Cập nhật state/DOM
}
```

### **React Implementation:**
```jsx
import { useEffect, useState } from 'react';

function TeamAnswersPage() {
    const [teamAnswers, setTeamAnswers] = useState([]);
    const [sseConnected, setSseConnected] = useState(false);

    useEffect(() => {
        // Kết nối SSE
        const eventSource = new EventSource('/api/team-answers/sse/');

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch(data.type) {
                case 'connected':
                    setSseConnected(true);
                    break;

                case 'create':
                    setTeamAnswers(prev => [data.data, ...prev]);
                    break;

                case 'delete':
                    setTeamAnswers(prev => 
                        prev.filter(item => !data.data.includes(item.id))
                    );
                    break;

                case 'heartbeat':
                    // Keep connection alive
                    break;
            }
        };

        eventSource.onerror = () => {
            setSseConnected(false);
        };

        // Cleanup
        return () => {
            eventSource.close();
        };
    }, []);

    return (
        <div>
            <div>SSE Status: {sseConnected ? '🟢 Connected' : '🔴 Disconnected'}</div>
            {/* Render team answers list */}
        </div>
    );
}
```

## 🔧 **Configuration**

### **Redis Settings:**
```python
# settings.py
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = 'your_password'  # Optional
REDIS_DB = 0
```

### **CORS Settings for SSE:**
```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True
```

## 🧪 **Testing**

### **Test SSE Service:**
```bash
python manage.py test_sse
```

### **Manual Testing:**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Django
python manage.py runserver

# Terminal 3: Test SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8000/api/team-answers/sse/

# Terminal 4: Create test team answer
curl -X POST http://localhost:8000/api/team-answers/ \
  -H "Content-Type: application/json" \
  -d '{"video_name": "test.mp4", "frame_index": 100, "url": "http://example.com"}'
```

## 📊 **Architecture**

```
Client Browser    Django Server    Redis Server
     |                 |               |
     |-- SSE Connect -->|               |
     |                 |-- Subscribe -->|
     |                 |               |
     |-- POST /team-answers/ -------->  |
     |                 |-- Save to DB   |
     |                 |-- Publish ---->|
     |<-- SSE Message --|<-- Message ---|
     |                 |               |
```

## 🚨 **Error Handling**

- **Redis không kết nối được**: SSE sẽ gửi error message và tiếp tục hoạt động
- **Client disconnect**: Redis subscription sẽ tự động cleanup
- **Network issues**: Client sẽ tự động reconnect (browser behavior)

## 🔄 **Production Considerations**

1. **Load Balancer**: Sử dụng sticky sessions hoặc Redis pub/sub cho multiple instances
2. **Connection Limits**: Monitor số lượng SSE connections
3. **Heartbeat**: Implement heartbeat để maintain connections
4. **Logging**: Monitor SSE performance và errors
5. **Security**: Implement authentication cho SSE endpoint nếu cần

## 📈 **Performance**

- **Memory**: Mỗi SSE connection sử dụng ~1MB RAM
- **Redis**: Pub/sub messages có overhead thấp
- **Network**: SSE messages được compress tự động
- **Scaling**: Horizontal scaling với Redis pub/sub
