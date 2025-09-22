# Link-check scheduler (xoay vòng trong 1 ngày)

Mục tiêu: Một vòng kiểm tra toàn bộ dữ liệu được chia thành 10 lát cắt (id % 10 = cursor),
chạy 10 lần/ngày (mỗi ~144 phút) để đi hết 10 lát trong đúng 1 ngày, và lần chạy nào cũng xóa link chết.

## 1) Chạy bằng cron trên server

- Tệp crontab mẫu: `scripts/cron/linkcheck_crontab`
- Script gọi API: `scripts/cron/run_linkcheck.sh`

Sửa `API_BASE` theo URL API của bạn (vd: http://api:8000 hoặc https://api.domain.com).
Sau đó cài crontab:

```bash
crontab /workspaces/ai-affiliate/scripts/cron/linkcheck_crontab
service cron restart  # nếu cần
```

Log mặc định ghi vào `/var/log/linkcheck.log` (bạn có thể đổi đường dẫn cho phù hợp).

Nếu API yêu cầu bearer token:
- Export `API_TOKEN` trong môi trường của cron hoặc sửa crontab để truyền `API_TOKEN="..."` trước lệnh.

## 2) Docker Compose (cron sidecar)

Tạo một service cron chạy kèm:

```yaml
services:
  api:
    image: your/api-image
    # ... cấu hình API

  linkcheck-cron:
    image: alpine:3.20
    command: ["/bin/sh", "-c", "crond -f -l 8"]
    volumes:
      - ./scripts/cron/run_linkcheck.sh:/usr/local/bin/run_linkcheck.sh:ro
      - ./scripts/cron/linkcheck_crontab:/etc/crontabs/root:ro
    environment:
      - API_BASE=http://api:8000
      # - API_TOKEN=xxxx
```

- Container `linkcheck-cron` sẽ gọi API 10 lần/ngày, đủ 1 vòng.

## 3) Kubernetes CronJob

Tạo CronJob chạy 10 lần/ngày (tần suất 144 phút). Ví dụ 00:00, 02:24, 04:48, ...

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: linkcheck-rotate
spec:
  schedule: "0 */2 * * *"  # mỗi 2 giờ; để đúng 10 lần/ngày, tạo nhiều CronJob lệch giờ hoặc dùng script điều phối
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: curl
              image: curlimages/curl:8.10.1
              args:
                - "-sS"
                - "-X"
                - "POST"
                - "$(API_BASE)/scheduler/linkcheck/rotate?delete_dead=true"
                - "--max-time"
                - "20"
                - "--retry"
                - "2"
                - "--fail"
              env:
                - name: API_BASE
                  value: "http://api:8000"
                # - name: API_TOKEN
                #   valueFrom:
                #     secretKeyRef: { name: api-token, key: token }
          restartPolicy: Never
```

Lưu ý: CronJob chuẩn chỉ cho lịch cố định (mỗi 2h = 12 lần/ngày). Để đúng 10 lần/ngày, bạn có thể:
- Tạo 5 CronJob khác nhau lệch giờ (mỗi cái 1 lần/4h, offset 0/24/48/72/96 phút) → tổng 10 lần/ngày.
- Hoặc dùng một service nội bộ điều phối theo thời điểm để đạt nhịp ~144 phút.

## 4) Tham số & vận hành

- Endpoint: `POST /scheduler/linkcheck/rotate?delete_dead=true`
- Hoạt động:
  - Dùng `linkcheck_cursor` (0..9) để chọn lát cắt `id % 10 = cursor`
  - Xoay `cursor` sau mỗi lần chạy
  - Trả về `{ cursor_used, next_cursor, scanned, alive, deleted }`
- Biến môi trường script:
  - `API_BASE`: bắt buộc, ví dụ `http://localhost:8000`
  - `API_TOKEN`: (tùy chọn) nếu API yêu cầu bearer token
  - `TIMEOUT`: (mặc định 20 giây)
  - `RETRIES`: (mặc định 2)

## 5) Kiểm tra nhanh

- Chạy thử một lần:

```bash
API_BASE=http://localhost:8000 ./scripts/cron/run_linkcheck.sh
```

- Kiểm tra trong Swagger nhóm Settings ⚙️ → `POST /scheduler/linkcheck/rotate`.

## 6) Tuỳ biến tần suất

- Mặc định: 10 lần/ngày (≈ 144 phút/lần) → hoàn thành 1 vòng/ngày.
- Nếu dữ liệu ít/nguy cơ link chết thấp, có thể giảm nhịp (ví dụ 6 lần/ngày) nhưng thời gian hoàn thành một vòng sẽ > 1 ngày.
- Nếu cần phản ứng nhanh, có thể tạm tăng nhịp (ví dụ 20 lần/ngày), sau 1–2 ngày giảm về nhịp 10 lần/ngày.
