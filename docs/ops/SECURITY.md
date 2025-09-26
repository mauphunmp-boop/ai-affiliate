## Bảo mật các endpoint quản trị

Các endpoint sau yêu cầu header `X-Admin-Key` nếu biến môi trường `ADMIN_API_KEY` được đặt:

| Endpoint | Mô tả |
|----------|------|
| `DELETE /metrics/web-vitals` | Xoá toàn bộ web vitals |
| `GET /system/logs` | Liệt kê file log JSONL |
| `GET /system/logs/{filename}` | Tail nội dung log |

### Cấu hình

1. Đặt biến môi trường:
```
ADMIN_API_KEY=your-strong-random-key
```
2. Khi gọi các endpoint trên, gửi header:
```
X-Admin-Key: your-strong-random-key
```

Nếu biến không được đặt, các endpoint vẫn mở (dùng cho môi trường dev cục bộ). Triển khai production nên luôn đặt.

### Gợi ý sinh key nhanh (PowerShell)
```powershell
[guid]::NewGuid().ToString('N')
```

Hoặc (Python):
```python
import secrets; print(secrets.token_hex(32))
```

### Lưu ý
- Không log admin key vào stdout / file.
- Có thể xoay khoá: cập nhật biến môi trường và restart service.
- Nếu tương lai bổ sung thêm thao tác nhạy cảm (import, trigger ingest force, xoá dữ liệu hàng loạt) hãy áp dụng cùng cơ chế này.
