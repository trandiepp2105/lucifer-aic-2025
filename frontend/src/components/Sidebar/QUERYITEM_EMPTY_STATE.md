# QueryItem Empty State Enhancement

## Vấn đề:
Khi một QueryItem không có nội dung nào (Text, OCR, Image đều trống), QueryItem sẽ hiển thị hoàn toàn trống, gây cảm giác trống trải và không thân thiện với người dùng.

## Giải pháp:
Luôn hiển thị ít nhất một field "Text:" với placeholder text khi QueryItem không có nội dung nào.

## Thay đổi đã thực hiện:

### 1. 🔧 **QueryItem.jsx - Logic Display:**

#### **Trước:**
```jsx
{/* Text field */}
{hasValidValue(query.text) && (
  <div className="sidebar__message-field">
    <strong>Text:</strong> {query.text}
  </div>
)}

{/* OCR field */}
{hasValidValue(query.ocr) && (
  <div className="sidebar__message-field">
    <strong>OCR:</strong> {query.ocr}
  </div>
)}

{/* Image field */}
{hasValidValue(query.image) && (
  <div className="sidebar__message-field">
    <img src={query.image} alt="Query image" />
  </div>
)}
```

#### **Sau:**
```jsx
{(() => {
  const hasText = hasValidValue(query.text);
  const hasOcr = hasValidValue(query.ocr);
  const hasImage = hasValidValue(query.image);
  const hasAnyContent = hasText || hasOcr || hasImage;

  return (
    <>
      {/* Text field - always show if has content, or show empty if no other content */}
      {(hasText || !hasAnyContent) && (
        <div className="sidebar__message-field">
          <strong>Text:</strong> {hasText ? query.text : <span className="sidebar__empty-field">Enter your query...</span>}
        </div>
      )}
      
      {/* OCR field */}
      {hasOcr && (
        <div className="sidebar__message-field">
          <strong>OCR:</strong> {query.ocr}
        </div>
      )}
      
      {/* Image field */}
      {hasImage && (
        <div className="sidebar__message-field sidebar__message-image">
          <img src={query.image} alt="Query image" className="sidebar__query-image" />
        </div>
      )}
    </>
  );
})()}
```

### 2. 🎨 **QueryItem.scss - Empty Field Styling:**

```scss
// Empty field placeholder styling
.sidebar__empty-field {
  color: #6c757d;
  font-style: italic;
  opacity: 0.7;
  font-size: 0.85rem;
}
```

## Logic hoạt động:

### **Kiểm tra nội dung:**
```javascript
const hasText = hasValidValue(query.text);
const hasOcr = hasValidValue(query.ocr);
const hasImage = hasValidValue(query.image);
const hasAnyContent = hasText || hasOcr || hasImage;
```

### **Điều kiện hiển thị Text field:**
```javascript
{(hasText || !hasAnyContent) && (
  // Hiển thị Text field nếu:
  // 1. Có text content HOẶC
  // 2. Không có content nào cả (để tránh trống)
)}
```

### **Nội dung Text field:**
```javascript
{hasText ? query.text : <span className="sidebar__empty-field">Enter your query...</span>}
// Nếu có text → hiển thị text
// Nếu không có text (và không có content nào) → hiển thị placeholder
```

## Kết quả:

### ✅ **Scenario 1: QueryItem có content**
- Có Text → Hiển thị "Text: [content]"
- Có OCR → Hiển thị "OCR: [content]" 
- Có Image → Hiển thị ảnh
- **Như trước, không thay đổi**

### ✅ **Scenario 2: QueryItem trống hoàn toàn**
- **Trước:** Hoàn toàn trống, chỉ có border
- **Sau:** Hiển thị "Text: *Enter your query...*" (italic, màu xám)

### ✅ **Scenario 3: QueryItem chỉ có OCR hoặc Image**
- **Trước:** Chỉ hiển thị OCR/Image, không có Text
- **Sau:** Vẫn chỉ hiển thị OCR/Image (không hiển thị Text trống)

## User Experience:

### **Benefits:**
1. **Không còn QueryItem trống** → Interface nhất quán
2. **Visual cue rõ ràng** → User biết đây là nơi nhập text
3. **Placeholder hướng dẫn** → "Enter your query..." gợi ý action
4. **Styling thân thiện** → Màu xám, italic, không chói mắt

### **Visual Design:**
- **Text content**: Màu đen, font bình thường
- **Empty placeholder**: Màu xám (#6c757d), italic, opacity 0.7
- **Size**: 0.85rem (nhỏ hơn content thật một chút)

## Files Modified:
- `/frontend/src/components/Sidebar/QueryItem.jsx`
- `/frontend/src/components/Sidebar/QueryItem.scss`

Bây giờ QueryItem sẽ không bao giờ trống hoàn toàn nữa! 🎉
