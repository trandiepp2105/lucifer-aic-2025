Tóm tắt các thay đổi đã thực hiện để giải quyết vấn đề 4 GET requests sau 1 POST:

## Vấn đề được phát hiện:
1. **ToastProvider không được tối ưu hóa**: Object `value` được tạo mới mỗi lần component render, gây ra useCallback trong TeamAnswer tạo mới function `fetchTeamAnswers`
2. **useEffect dependency không tối ưu**: useEffect phụ thuộc vào `fetchTeamAnswers` khiến mỗi khi function này tạo mới, useEffect sẽ chạy lại

## Các thay đổi đã thực hiện:

### 1. Tối ưu hóa ToastProvider
- Thêm `useCallback` cho `showToast` và `removeToast`
- Sử dụng `useMemo` cho object `value` để tránh tạo mới không cần thiết

### 2. Tối ưu hóa TeamAnswer component
- Thay đổi useEffect dependency từ `[isVisible, fetchTeamAnswers]` thành `[isVisible, queryIndex, round]`
- Chuyển `fetchTeamAnswers` từ useCallback thành function thường
- Thêm logging để debug số lần render và useEffect trigger

### 3. Thêm endpoint /api/team-answers/delete-all/
- Tạo view `TeamAnswerBulkDeleteAPIView` trong backend
- Thêm URL pattern cho bulk delete endpoint
- Cập nhật documentation

## Kết quả mong đợi:
- Giảm số lượng GET requests không cần thiết sau khi POST
- Component chỉ fetch data khi thực sự cần thiết (khi isVisible, queryIndex, hoặc round thay đổi)
- Cải thiện performance tổng thể
