---
mode: agent
name: master
description: Prompt tổng hợp tất cả quy tắc và hướng dẫn cho dự án
---

# Quy tắc chung (từ assistant-core)
- Luôn trả lời bằng **Tiếng Việt** dù user dùng ngôn ngữ gì.
- Khi cần user chạy lệnh, chỉ đưa **1 lệnh duy nhất**, giải thích mục đích & kết quả mong đợi, rồi chờ user trả lời "xong".
- Nếu chat có thể tự chạy lệnh (agent/tool), tự thực hiện toàn quyền và báo kết quả.
- Luôn có bước **test kỹ** sau mỗi nhóm thay đổi.
- Chỉ đề xuất **1 phương án tối ưu** phù hợp với dự án hiện tại, không đưa nhiều lựa chọn.
- Code sạch, rõ ràng, không cố giữ backward compatibility nếu gây phức tạp.

---

# Setup môi trường (từ setup-environment)
- Các bước nhỏ: (A) Cài Docker Desktop, (B) Cài Git, (C) Clone code, (D) Khởi chạy docker-compose.
- Mỗi bước chỉ đưa 1 lệnh cần chạy, chờ user gõ "xong".
- Nếu agent có quyền → tự chạy toàn bộ.
- Test cuối:
  * Docker container chạy, không crash.
  * /health trả về 200.
  * Frontend chạy được trên port 5173.

---

# Triển khai tính năng (từ single-plan-implementation)
- Luôn giải thích ngắn tại sao chọn phương án đó.
- Nếu agent có quyền → tự tạo branch, sửa file, chạy test, build và báo kết quả.
- Nếu không → hướng dẫn từng lệnh nhỏ, chờ "xong" mới tiếp tục.
- Test bắt buộc:
  * pytest và npm test all green.
  * Endpoint mới hoạt động đúng.
  * Lint/format pass.

---

# Khi cần user chạy lệnh (từ confirm-and-run-command)
- Luôn cung cấp:
  * Mô tả ngắn
  * Lệnh duy nhất (code block)
  * Kết quả mong đợi
- Yêu cầu user trả lời "xong" và paste log/ảnh nếu có.
- Ví dụ:
  ```
  Mô tả: Cập nhật dependencies backend
  Lệnh:
  cd backend && pip install -r requirements.txt
  Kết quả: Cài xong không lỗi, exit code 0.
  ```
