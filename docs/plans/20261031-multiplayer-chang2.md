# Brief: NeonPool chơi đôi — Chặng 2: mã phòng qua internet (2026-10-31)

Nối tiếp `20261030-multiplayer.md` (Chặng 0+1) và `20261031-multiplayer-chang3.md` (Chặng 3). Luật chơi: `docs/GAME_DESIGN.md` "Chơi mạng" + "Phản hồi lần 20". Kiến trúc: `docs/ARCHITECTURE.md` "Chơi mạng".
Người dùng chốt 2026-10-31: làm Chặng 2 (Chặng 4 sau khi chơi thử); máy trung chuyển trên Cloudflare (miễn phí, không thẻ); mã phòng 4 chữ cái; mất internet thì không chơi được (không giữ ô gõ địa chỉ); cùng wifi thì tự nối thẳng.

## Yêu cầu (đo được)
- Tạo phòng → hiện mã 4 chữ (bỏ I, L, O); Vào phòng → gõ mã → vào ván. Màn hình không còn hiện địa chỉ mạng.
- Hai máy cùng mạng: nối thẳng nếu được trong `NET_LAN_TRY_S` (0,6 s), không thì qua máy trung chuyển. Người chơi không chọn.
- Mọi thứ Chặng 3 giữ nguyên qua máy trung chuyển: rớt mạng/vào lại 60 s, Đấu lại, đầu hàng, đồng hồ, biểu cảm.
- Lỗi báo rõ: không có mạng / máy chủ, không thấy phòng, phòng đủ người, máy chủ quá tải, khác bản.
- Máy trung chuyển chỉ chuyển tin, KHÔNG chạy vật lý hay luật; chủ phòng vẫn là trọng tài.
- Một chiều "thả chuột → máy kia áp cú" ≤ 50 ms p95 (qua Singapore dự kiến 40–60): ĐO SAU KHI ĐƯA LÊN, ghi nhãn thật/giả lập.
- Tập một mình KHÔNG đổi (AC1).

## Quyết định kỹ thuật (và lý do)
| Chủ đề | Quyết định | Lý do |
|---|---|---|
| Máy trung chuyển | Cloudflare Worker + Durable Object (`server/cloudflare/`, JavaScript), mỗi mã phòng một object, `locationHint: "apac"` | miễn phí không thẻ, không có máy để tự trông; object nằm gần người tạo phòng |
| Đường nối | WebSocket (`wss://`), mỗi khung game = một tin nhị phân nguyên vẹn; tin điều khiển là JSON chữ. Thư viện `websockets` (bản đồng bộ, luồng nền) | Cloudflare chỉ nhận HTTP/WebSocket, không UDP. Mất gói vẫn chờ chặn như TCP (đã đo ở Chặng 0: p99 ~220 ms khi mất 2%) — chấp nhận, ghi lại |
| Bản chạy máy mình | `server/local_relay.py` (Python, cùng giao thức) cho test, smoke, công cụ dev; bộ test giao thức chạy được trên CẢ hai bản (`NEONPOOL_RELAY_TEST_URL` trỏ tới `wrangler dev`) | test không cần internet; hai bản không lệch nhau |
| Giao thức trung chuyển v1 | `GET /v1/look?code=` (xem phòng, lấy thông tin nối thẳng) · WS `/v1/host[?code&key]` (tạo / lấy lại phòng) · WS `/v1/join?code=` · chủ nhận `peer on n / off`, trả `ack n`; tin của chủ chỉ tới khách sau `ack` | khung cũ của chủ không lọt sang người vào sau |
| Đứt một phía = đứt cả kênh | chủ mất kết nối → máy trung chuyển đóng luôn đường của khách, giữ phòng 90 s cho chủ lấy lại bằng `key`; khách mất → chủ nhận `peer off` | `Session` của Chặng 3 (Resume + token + dán bàn) lo phần còn lại; không có khung nào mất mà hai bên tưởng còn nối |
| Khách cũ treo | người vào mới thay chỗ khách cũ nếu khách cũ im > 4 s (game ping mỗi 1 s) | wifi đổi mạng thì đường cũ treo hàng phút ở máy chủ; không thì khách không vào lại được |
| Nối thẳng | chủ mở `TcpListener` (cổng `NET_PORT`, bận thì cổng bất kỳ) + chuỗi bí mật 16 byte, gửi "địa chỉ LAN + bí mật" qua máy trung chuyển (không hiện ra màn hình); khách thử nối thẳng có bí mật trước, quá 0,6 s thì vào qua máy trung chuyển | người cùng wifi mà không có mã thì không lọt vào; người chơi không thấy địa chỉ |
| Mã phòng | 4 chữ trong `ABCDEFGHJKMNPQRSTUVWXYZ` (23⁴ ≈ 280 nghìn), máy trung chuyển cấp, trùng thì cấp lại | người dùng chọn; bỏ I/L/O dễ nhầm với 1/0 |
| Phòng bỏ quên | phòng chưa có khách quá 30 phút thì máy trung chuyển đóng | giữ mức miễn phí (thời gian object chạy) |
| Địa chỉ máy trung chuyển | `config.NET_RELAY_URL`; `NEONPOOL_RELAY_URL` thay (test, dev). Rỗng = chưa đưa lên → báo "không có máy chủ" | địa chỉ thật chỉ biết sau khi đưa lên tài khoản của người dùng |

## Task (mỗi task một commit)
1. Tài liệu (commit này): brief, ARCHITECTURE, GAME_DESIGN lần 20.
2. `server/local_relay.py` + `game/net/relay.py` (`WsTransport`, `HostRoom`, `Join`, hai `Relinker`) + `tcp.py` (bí mật nối thẳng) + test (AC18–AC21).
3. `server/cloudflare/` (Worker + Durable Object) + chạy bộ test giao thức trên `wrangler dev` (AC22).
4. Phác giao diện (mã phòng, ô gõ mã, lỗi) → người dùng chọn.
5. Bảng Chơi theo hướng được chọn + chữ vi/en + Hướng dẫn trang Chơi đôi + công cụ dev.
6. Smoke hai game qua máy trung chuyển cục bộ (AC8); `netbench.py --relay`; PROGRESS; cổng đầy đủ.
7. (KHI NGƯỜI DÙNG NÓI) đưa lên Cloudflare, điền `NET_RELAY_URL`, đo thật.

## Tiêu chí chấp nhận → test
| # | Tiêu chí | Test |
|---|---|---|
| AC18 | tạo phòng có mã đúng dạng; vào bằng mã → khung đi hai chiều đúng thứ tự; mã sai / phòng đủ người / phòng đã đóng báo đúng lỗi | `test_ac18_*` trong `tests/test_net_relay.py` |
| AC19 | chủ hoặc khách đứt → cả kênh đứt; chủ lấy lại phòng bằng key, khách vào lại; khung cũ của chủ không tới khách mới; khách cũ treo bị thay | `test_ac19_*` |
| AC20 | cùng máy có nối thẳng → dùng nối thẳng; nối thẳng hỏng → qua trung chuyển; không có bí mật thì không vào được cửa thẳng | `test_ac20_*` |
| AC21 | ván hai `Session` qua máy trung chuyển: rớt giữa ván rồi vào lại → `same_table`, ván xong cùng kết quả | `test_ac21_*` |
| AC22 | bộ test giao thức xanh trên bản Cloudflare chạy máy mình (`wrangler dev`) | `NEONPOOL_RELAY_TEST_URL=... pytest tests/test_net_relay.py` (ghi kết quả ở đây) |
| AC23 | bảng Chơi: mã hiện, gõ mã, lỗi; vi/en cùng bộ khoá; ảnh đã nhìn ở 1280×720 và 1050×590 | `test_net_play.py`, `test_i18n.py`, `tools/_out/20261031-ma-phong/` |
