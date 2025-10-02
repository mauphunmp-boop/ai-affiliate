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

---

# Checklist test (từ testing-checklist)
1. Unit test: pytest -q (all green).
2. Lint & format: black . --check, ruff ., eslint . (pass).
3. Integration: docker-compose up → /health 200.
4. Manual:
   * Tạo 1 product qua API.
   * Gọi /ai/suggest → kết quả hợp lệ.
5. Rollback nếu fail: git checkout -- <file> hoặc docker-compose down --rmi local.

---

# Code style (từ code-style-guideline)
- Ưu tiên readability, tách module ≤400 dòng.
- Docstring cho mỗi function công khai.
- Không cố giữ API cũ nếu làm code phức tạp.
- Dùng typing (Python), propTypes/interface (JS).
- Có test cho logic chính.
- Commit message dạng: feat/bugfix/<short-descr>.
- Ví dụ: `feat: add /ingest/v2 full datafeeds (no pagination)`

---

# Deploy dev (từ finalize-and-deploy-dev)
- Quy trình: feature branch → PR → test → merge develop.
- Nếu agent có CI quyền → build image, push, docker-compose dev up.
- Nếu không → user chạy 3 lệnh:
  1. git checkout -b feat/... && git add . && git commit -m "feat: ..." && git push origin feat/...
  2. docker-compose -f docker-compose.dev.yml up --build -d
  3. curl -sS http://localhost:8000/health
- Sau deploy: chạy lại checklist testing-checklist.
