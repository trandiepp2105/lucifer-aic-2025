# QueryInput Navigation and Speech Input Changes

## Thay đổi đã thực hiện:

### 1. 🎯 Thay đổi Keyboard Navigation
**Trước:** Sử dụng `ArrowUp` / `ArrowDown` để di chuyển giữa các input
**Sau:** Sử dụng `Ctrl + ArrowUp` / `Ctrl + ArrowDown`

**Lý do:** Tránh xung đột với việc di chuyển cursor trong textarea khi người dùng đang gõ.

```javascript
// Trước:
if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {

// Sau:
if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && e.ctrlKey) {
```

### 2. 🚫 Tạm thời vô hiệu hóa Speech Input
**Lý do:** Chưa sẵn sàng sử dụng, nhưng giữ code để dễ kích hoạt lại sau này.

#### Các phần đã comment:

1. **Refs và Input Array:**
   ```javascript
   // const speechTextareaRef = useRef(null); // Commented out
   const inputRefs = [ocrTextareaRef, textareaRef]; // Removed speechTextareaRef
   ```

2. **Auto-resize function:**
   ```javascript
   // const adjustSpeechTextareaHeight = () => { ... } // Commented out
   ```

3. **useEffect hooks:**
   ```javascript
   // useEffect for speech auto-resize - Commented out
   // adjustSpeechTextareaHeight() call - Commented out
   ```

4. **Translation function:**
   ```javascript
   // const handleTranslateSpeech = async () => { ... } // Commented out
   ```

5. **JSX Speech Input Section:**
   ```jsx
   {/* Speech Text Input Section - COMMENTED OUT */}
   {/* <div className="sidebar__input-section">...</div> */}
   ```

6. **Send button logic:**
   ```javascript
   // Removed speech validation from send button disabled condition
   ```

#### Navigation Logic Update:
```javascript
// Trước: OCR(0) -> Speech(1) -> Text(2)
// Sau:  OCR(0) -> Text(1)
const inputRefs = [ocrTextareaRef, textareaRef];
```

## Kết quả:

### ✅ **Hoạt động hiện tại:**
- ✅ Navigation: `Ctrl + ↑` / `Ctrl + ↓` giữa OCR và Text input
- ✅ OCR input: Hoạt động bình thường với translate button
- ✅ Text input: Hoạt động bình thường
- ✅ Image upload: Hoạt động bình thường
- ✅ Send button: Chỉ kiểm tra Text, OCR và Image (bỏ Speech)

### 🔧 **Để kích hoạt lại Speech input:**
1. Uncomment tất cả các dòng có `// Commented out` hoặc `/* ... */`
2. Thêm lại `speechTextareaRef` vào `inputRefs` array
3. Update navigation logic trở lại 3 inputs
4. Update focus index cho text input từ 1 về 2
5. Thêm lại speech validation vào send button

### 📝 **Files đã thay đổi:**
- `/frontend/src/components/Sidebar/QueryInput.jsx`

### 🎯 **User Experience:**
- Navigation không còn xung đột với việc di chuyển cursor trong textarea
- Giao diện sạch hơn (bỏ Speech input chưa sử dụng)
- Keyboard shortcuts rõ ràng: `Ctrl + Arrow keys` cho navigation
