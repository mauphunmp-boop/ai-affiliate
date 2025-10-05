# Hướng dẫn thiết lập Ubuntu Server trên máy Dell (chạy liên tục, phân vùng đĩa tối ưu, bảo mật, deploy)

Tài liệu này giúp bạn biến máy Dell chạy Ubuntu thành server ổn định cho dự án "AI Affiliate Advisor" theo các mục tiêu: tách dữ liệu, tối ưu I/O và RAM, an toàn dữ liệu, dễ deploy/backup và bảo mật truy cập.

## 1) Cấu hình chạy liên tục khi gập nắp (lid close)

Mục tiêu: Máy không sleep/suspend khi gập nắp, vẫn chạy Docker/SSH.

Các bước:
1. Sửa logind.conf:
   - Mở: `/etc/systemd/logind.conf`
   - Đặt:
     - `HandleLidSwitch=ignore`
     - `HandleLidSwitchDocked=ignore`
     - (tùy chọn) `IdleAction=ignore`
2. Áp dụng: `systemctl restart systemd-logind`
3. Kiểm tra BIOS/UEFI (Dell): tắt các tuỳ chọn sleep khi AC plugged nếu cần.

Lưu ý: Nếu dùng Desktop Environment, kiểm tra thêm Power Settings để tắt sleep.

## 2) Kiểm tra phần cứng & dung lượng đĩa

- RAM: 12 GB (mục tiêu: dành ~2–4 GB cho OS + Docker daemon, ~6–8 GB cho backend/DB cache)
- SSD ~ 119 GB (đang cài hệ điều hành)
- HDD 500 GB (sẽ xoá sạch; dùng cho dữ liệu Postgres và lưu trữ logs/artifacts)

Lệnh tham khảo (tuỳ chọn chạy):
- Kiểm tra đĩa: `lsblk -f`, `df -h`, `sudo fdisk -l`
- SMART: `sudo smartctl -a /dev/sdX`

## 3) Kiến trúc phân chia lưu trữ

- SSD (119 GB): Hệ điều hành + mã nguồn + image cache (build nhanh) + logs hệ thống nhỏ
  - Thư mục dự án: `/home/<user>/projects/ai-affiliate` (git clone)
  - Docker images/layers mặc định ở SSD để tốc độ build tốt

- HDD (500 GB): Dữ liệu runtime nặng I/O
  - Postgres data: `/data/postgres` (bind mount vào container)
  - Logs lớn/archives: `/data/logs`
  - Backups: `/data/backups`

Lợi ích: tách I/O application (SSD) và I/O dữ liệu (HDD), hạn chế cạnh tranh đọc/ghi.

### 3.1) Chuẩn bị HDD (xoá sạch dữ liệu và mount vào /data)

1. Xác định thiết bị HDD (ví dụ `/dev/sdb`).
2. Xoá phân vùng cũ và tạo mới (ext4):
   - Dùng `parted` hoặc `fdisk` tạo một phân vùng chính toàn bộ đĩa.
   - Format: `sudo mkfs.ext4 -L data /dev/sdb1`
3. Tạo mountpoint và mount:
   - `sudo mkdir -p /data`
   - Lấy UUID: `blkid /dev/sdb1`
   - Thêm vào `/etc/fstab`: `UUID=<uuid>  /data  ext4  defaults,noatime  0  2`
   - `sudo mount -a` và kiểm tra `df -h /data`

Tham số `noatime` giảm ghi đĩa không cần thiết.

## 4) Cài Docker & Docker Compose

1. Cài Docker Engine theo hướng dẫn chính thức (apt repo của Docker).
2. Thêm user vào nhóm docker: `sudo usermod -aG docker <user>` (logout/login lại)
3. Kiểm tra: `docker run hello-world`
4. Cài docker compose plugin (nếu chưa có): `docker compose version`

## 5) Người dùng, SSH và firewall

- Tạo user không phải root, thêm vào sudo & docker groups.
- SSH:
  - Bật xác thực bằng key, tắt password (sửa `/etc/ssh/sshd_config`: `PasswordAuthentication no`, `PermitRootLogin no`).
  - Mở port 22 trên firewall.
- Firewall: UFW bật mặc định deny, allow 22/tcp, 8000/tcp, 5173/tcp (hoặc dùng reverse proxy 80/443 phía trước).

## 6) Deploy dự án và run services

Clone repo vào SSD (thư mục home). Chuẩn bị .env (bí mật `AFF_SECRET`).

Sử dụng file `docker-compose.prod.yaml` (đã thêm):

- Postgres bind mount về `/data/postgres` trên HDD
- web và frontend đặt `restart: always`

Chạy:
- `docker compose -f docker-compose.prod.yaml up -d --build`

Kiểm tra:
- Backend: `curl http://localhost:8000/health`
- Frontend: `curl http://localhost:5173` (dev server) hoặc triển khai build production với reverse proxy nếu cần public.

Gợi ý production frontend:
- Build `vite build` tạo `dist/`, phục vụ qua nginx/caddy (map 80/443), proxy backend qua `/api` → `http://web:8000`.

## 7) Backup và an toàn dữ liệu

- Postgres:
  - Lịch `pg_dump` định kỳ ra `/data/backups/pg/` (kèm timestamp), giữ 7–30 bản gần nhất.
  - Tuỳ chọn rsync/s3 sync folder backup ra thiết bị ngoài.
- Logs: quay vòng logs với `logrotate` cho `/data/logs`.

## 8) Tối ưu hiệu năng

- Postgres tuning (thận trọng theo RAM):
  - `shared_buffers`: ~25% RAM (tuỳ mức sử dụng, ví dụ 3GB cho 12GB RAM tổng, cân nhắc các dịch vụ khác)
  - `effective_cache_size`: ~50–60% RAM
  - `work_mem`: nhỏ nhưng đủ (4–16MB) tuỳ workload
  - `maintenance_work_mem`: 256–512MB cho VACUUM/CREATE INDEX
- Docker: tránh container ngốn hết RAM; có thể đặt `--memory`/`--cpus` nếu cần.
- OS: dùng `noatime` ở /data; theo dõi `iostat`, `vmstat`.

## 9) Cập nhật từ GitHub và CI đơn giản

- Cập nhật thủ công:
  - `git pull`
  - `docker compose -f docker-compose.prod.yaml up -d --build`
- Tuỳ chọn thiết lập webhook → script pull & rebuild.

## 10) Bảo mật bổ sung

- Fail2ban cho SSH
- Đặt reverse proxy TLS (Let’s Encrypt) nếu public
- Giới hạn quyền trên `/data/*` (chỉ user dịch vụ)

---

Checklist nhanh:
- [ ] Lid close: ignore (systemd-logind + DE)
- [ ] HDD format + mount `/data` trong fstab (noatime)
- [ ] Docker + user group docker
- [ ] UFW rules + SSH key auth
- [ ] .env bí mật + compose prod chạy ok
- [ ] Backup cron pg_dump sang `/data/backups`
