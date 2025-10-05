# Cloudflare Tunnel (public access)

Kết nối các dịch vụ chạy trong server tới domain công khai qua Cloudflare Tunnel mà không cần mở cổng inbound trên firewall.

## Yêu cầu
- Dịch vụ đã chạy nội bộ trên server:
  - Backend API: http://localhost:8000 (FastAPI)
  - Admin frontend: http://localhost:5173 (tạm dùng Vite dev)
- Tài khoản Cloudflare đã quản lý domain của bạn. Ví dụ hostnames:
  - admin.<your-domain> → React admin
  - api.<your-domain> → FastAPI API
  - <your-domain> (apex) → landing/chat (tạm proxy vào FastAPI)

## Cài đặt cloudflared (Ubuntu)
```bash
sudo install -d -m 0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
CODENAME=$(. /etc/os-release; echo $VERSION_CODENAME)
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared ${CODENAME} main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
sudo apt-get update
sudo apt-get install -y cloudflared
cloudflared --version
```

## Đăng nhập và tạo Tunnel
```bash
# Mở trình duyệt để xác thực (nếu headless, copy URL hiển thị ra trình duyệt)
cloudflared tunnel login

# Tạo tunnel tên dễ nhớ (khuyên dùng: core-backend)
cloudflared tunnel create core-backend
# Lệnh trên in ra UUID và lưu credentials JSON vào /etc/cloudflared/<UUID>.json (nếu chạy bằng root)
# hoặc ~/.cloudflared/<UUID>.json (nếu chạy bằng user thường).

# Tuỳ chọn không cần cert.pem: tạo token cho tunnel (qua Cloudflare Dashboard hoặc CLI)
# Sau khi tạo, lưu token vào file (ví dụ):
#   sudo install -d -m 0750 /etc/cloudflared
#   sudo bash -lc 'printf %s "<PASTE_TUNNEL_TOKEN>" > /etc/cloudflared/token && chmod 640 /etc/cloudflared/token'
```

## Cấu hình ingress và DNS
Tạo file /etc/cloudflared/config.yml (đổi hostname theo domain của bạn). Có hai cách chạy: dùng credentials-file hoặc dùng token (khuyên dùng token để tránh lỗi cert.pem).

```yaml
# /etc/cloudflared/config.yml

# Tên/UUID tunnel đã tạo ở bước trước
tunnel: core-backend

# Nếu chạy theo chế độ credentials-file (không dùng token) thì giữ dòng dưới và trỏ đúng file JSON:
# credentials-file: /etc/cloudflared/<UUID>.json
# Nếu chạy bằng token (không cần cert.pem) thì BỎ dòng credentials-file này đi.

# Quy tắc ingress (thứ tự quan trọng)
ingress:
  - hostname: admin.<your-domain>
    service: http://localhost:5173
  - hostname: api.<your-domain>
    service: http://localhost:8000
  - hostname: <your-domain>
    service: http://localhost:8000
  - service: http_status:404
```

Tạo DNS records trỏ hostname vào tunnel (CNAME do Cloudflared quản lý):
```bash
cloudflared tunnel route dns core-backend admin.<your-domain>
cloudflared tunnel route dns core-backend api.<your-domain>
cloudflared tunnel route dns core-backend <your-domain>
```

## Chạy bằng token (không cần cert.pem)

Chạy thử foreground để debug (lưu ý: đặt cờ toàn cục trước subcommand `tunnel`):

```bash
# Đọc token (cần sudo nếu token nằm trong /etc/cloudflared/token)
export TUNNEL_TOKEN="$(sudo cat /etc/cloudflared/token)"

# Chạy foreground với log debug, dùng config.yml (không truyền UUID/NAME ở cuối)
cloudflared --loglevel debug --config /etc/cloudflared/config.yml tunnel run
```

Dấu hiệu chạy đúng: thấy log "Connected to ..." và không còn lỗi "Cannot determine default origin certificate path".

## Chạy như một dịch vụ (systemd)

Khuyên dùng chạy bằng token qua biến môi trường để tránh phụ thuộc cert.pem/credentials-file:

```bash
# 1) Lưu token vào biến môi trường qua file /etc/default/cloudflared
echo 'TUNNEL_TOKEN=<PASTE_TUNNEL_TOKEN>' | sudo tee /etc/default/cloudflared >/dev/null
sudo chmod 640 /etc/default/cloudflared

# 2) Tạo/ cập nhật unit
sudo tee /etc/systemd/system/cloudflared.service >/dev/null <<'UNIT'
[Unit]
Description=Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/default/cloudflared
ExecStart=/usr/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml --loglevel info tunnel run
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
systemctl status cloudflared --no-pager
journalctl -u cloudflared -n 100 --no-pager
```

## Kiểm thử
- https://api.<your-domain>/health → 200 từ FastAPI.
- https://admin.<your-domain> → trang index của Vite dev (tạm thời).
- https://<your-domain> → proxy về FastAPI.

## Ghi chú
- Không cần mở cổng inbound; UFW có thể chỉ mở SSH.
- Đổi backend/ingress sau này: sửa /etc/cloudflared/config.yml rồi:
  ```bash
  sudo systemctl restart cloudflared
  ```
- Khi triển khai frontend production (bundle tĩnh), đổi service target sang cổng/đường dẫn mới.

### Cảnh báo ICMP proxy (tuỳ chọn)
Nếu thấy cảnh báo kiểu "The user running cloudflared process has a GID that is not within ping_group_range" và ICMP proxy bị tắt, bạn có thể bật quyền ping cho user không phải root bằng sysctl:

```bash
echo 'net.ipv4.ping_group_range = 0 2147483647' | sudo tee /etc/sysctl.d/99-cloudflared-icmp.conf
sudo sysctl --system
```
Điều này không bắt buộc cho hoạt động của tunnel (chỉ ảnh hưởng tới ICMP health/checks).
