# Local Query Management Refactor

## Thay đổi được thực hiện:

### 1. 🗑️ **Loại bỏ `filteredLocalQueries`**
- **Trước:** Sử dụng `filteredLocalQueries = localQueries` làm layer trung gian
- **Sau:** Dùng trực tiếp `localQueries` trong SidebarQueries

```javascript
// Trước:
const filteredLocalQueries = localQueries;
<SidebarQueries filteredQueries={filteredLocalQueries} />

// Sau:
<SidebarQueries filteredQueries={localQueries} />
```

### 2. 🔄 **Cơ chế cập nhật mới**
**Trước:** `currentLocalQuery` độc lập, chỉ gửi lên server khi submit
**Sau:** Cập nhật trực tiếp vào `localQueries`, QueryItem reference cùng object

#### Cơ chế hoạt động:
```javascript
const updateCurrentLocalQuery = useCallback((updates) => {
  setLocalQueries(prev => {
    const currentStageIndex = prev.findIndex(q => q.stage === stage);
    
    if (currentStageIndex >= 0) {
      // Update existing query for current stage
      const updatedQueries = [...prev];
      updatedQueries[currentStageIndex] = {
        ...updatedQueries[currentStageIndex],
        ...updates,
        updated_at: new Date().toISOString()
      };
      return updatedQueries;
    } else {
      // Create new query for current stage
      const newQuery = createLocalQuery({ stage: stage, ...updates });
      return [...prev, newQuery];
    }
  });

  // Also update currentLocalQuery for input synchronization
  setCurrentLocalQuery(prev => ({ ...prev, ...updates, updated_at: new Date().toISOString() }));
}, [stage, createLocalQuery]);
```

### 3. 📋 **Luồng dữ liệu mới:**

```
User Input → updateCurrentLocalQuery → Updates localQueries[stage] → QueryItem auto-reflects changes
                                   ↳ Updates currentLocalQuery (for input binding)

Press Enter → handleSendMessage → Send to server → Reload from server → Update localQueries
```

### 4. 🎯 **Lợi ích của cơ chế mới:**

#### **Real-time Local Updates:**
- Khi user type ở stage 1 → QueryItem stage 1 cập nhật ngay lập tức
- Khi chuyển sang stage 2, type input → QueryItem stage 2 cập nhật ngay lập tức
- Khi quay lại stage 1 → Thấy nội dung đã nhập trước đó

#### **Object Reference Sharing:**
- QueryItem và input fields reference cùng data object
- Thay đổi ở input → QueryItem tự động reflect
- Không cần manual sync giữa các components

#### **Lazy Server Sync:**
- Chỉ gửi lên server khi nhấn Enter
- Cho phép edit local trước khi commit
- Reduce server calls

### 5. 🔧 **Technical Implementation:**

#### **State Management:**
- `localQueries`: Array chứa tất cả queries, mỗi item có field `stage`
- `currentLocalQuery`: Copy của query đang edit (để bind với input)
- `updateCurrentLocalQuery`: Function update cả 2 states đồng thời

#### **Stage Navigation:**
- Khi đổi stage → Load query tương ứng từ `localQueries[stage]`
- Nếu stage chưa có query → Tạo empty query cho stage đó
- Input changes → Cập nhật vào `localQueries[currentStage]`

#### **Server Sync:**
- Enter/Send → Lấy data từ `currentLocalQuery` gửi server
- Server response → Reload `localQueries` từ server
- Đảm bảo consistency giữa local và server state

### 6. 🚀 **User Experience:**

#### **Trước:**
1. User type → Chỉ currentLocalQuery thay đổi
2. QueryItem không thể hiện changes realtime
3. Phải save rồi reload để thấy changes

#### **Sau:**
1. User type → Cả currentLocalQuery và localQueries[stage] đều thay đổi
2. QueryItem hiển thị changes ngay lập tức
3. Real-time preview trong sidebar while typing
4. Local edits persist khi chuyển stage
5. Chỉ commit to server when press Enter

### 7. 📝 **Files Modified:**
- `/frontend/src/components/Sidebar/Sidebar.jsx`:
  - Removed `filteredLocalQueries`
  - Updated `updateCurrentLocalQuery` logic
  - Modified SidebarQueries props

### 8. 🔮 **Next Steps:**
- Test stage switching với local changes
- Verify QueryItem real-time updates
- Ensure server sync works correctly
- Test edge cases (empty stages, conflicts, etc.)
