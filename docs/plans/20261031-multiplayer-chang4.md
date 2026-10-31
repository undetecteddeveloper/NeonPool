# Brief: NeonPool chơi đôi — Chặng 4: theo dõi và vận hành máy trung chuyển (2026-10-31)

Nối tiếp `20261031-multiplayer-chang2.md`. Người dùng chốt 2026-10-31: làm đủ 4 phần; xem bằng LỆNH trên máy mình (không có trang web); báo sập bằng email; GIỮ NGUYÊN độ trễ (không làm gì thêm để giảm). Người chơi KHÔNG thấy gì đổi trong game.

## Yêu cầu (đo được)
- `tools\relay_ops.py status`: bảng chữ ngay trong cửa sổ lệnh — số phòng và từng phòng (mã, đang chờ / đang chơi / chủ mất kết nối, tuổi, ping giữa hai người), số hôm nay (phòng mới, lượt vào, khung tin, % mức miễn phí ước tính), 20 dòng nhật ký cuối.
- Nhật ký có LÝ DO: mỗi lần phòng mở, khách vào / ra, chủ ra / vào lại, phòng đóng đều ghi giờ + mã + lý do (`host_closed`, `idle`, `expired`, `host_link`, `guest_link`, `guest_replaced`). Giữ 200 dòng cuối.
- `tools\relay_ops.py deploy`: MỘT lệnh cập nhật máy chủ thật: chạy test giao thức trên bản máy mình → `wrangler deploy` → hỏi `/v1/health` → in kết quả. Đỏ ở bước nào thì dừng ở bước đó, nói rõ.
- Báo sập: `GET /v1/health` trả 200 khi khoẻ, 503 khi mức miễn phí ước tính ≥ 90%. Email do dịch vụ theo dõi bên ngoài gửi (xem "Khác ý người dùng"), không phải Cloudflare.
- Máy trung chuyển vẫn KHÔNG đọc khung game; `stat` chỉ là một con số ping do chủ phòng khai.

## Khác điều người dùng chọn (đã tra, ghi để hỏi lại nếu muốn khác)
Người dùng chọn "email tới smithnguyen247@gmail.com". Tra 2026-10-31: gói miễn phí của Cloudflare không gửi được email từ Worker (gửi cho người bất kỳ cần gói trả phí; gói miễn phí chỉ nhận thư) và không có thông báo "Worker sập" miễn phí; một Worker cũng không tự báo được khi chính nó sập hay hết lượt. Nên email do dịch vụ theo dõi bên ngoài (UptimeRobot, miễn phí, kiểm 5 phút một lần) gửi, trỏ vào `/v1/health`. Người dùng phải tự đăng ký (Claude không làm hộ được tài khoản): các bước ở `tools\relay_ops.py setup`.

## Quyết định kỹ thuật (và lý do)
| Chủ đề | Quyết định | Lý do |
|---|---|---|
| Sổ chung | Durable Object `Hub` (một object tên cố định) giữ: danh sách phòng đang sống, nhật ký 200 dòng, số liệu trong ngày (UTC) | mỗi phòng là một object riêng nên không ai biết "có mấy phòng" |
| Phòng báo sổ | `Room` báo `Hub` khi có sự kiện (không bao giờ theo từng khung) + mỗi 5 phút nếu có khung mới (để số liệu không cũ) | giữ mức miễn phí: mỗi báo là một yêu cầu |
| Xem trực tiếp | `status` hỏi `Hub`, `Hub` hỏi từng phòng sống lấy trạng thái + ping hiện tại | ping luôn mới mà không tốn yêu cầu khi không ai xem |
| Ping | chủ phòng gửi `{"t":"stat","rtt":ms}` mỗi 10 s khi có khách (số ping `Session.rtt_s` đã đo) | máy trung chuyển không thấy được ping giữa hai người; không đổi giao thức game |
| Mức miễn phí | `used_pct` = (khung/20 + số sự kiện) / 100000 hôm nay. Là ƯỚC, thấp hơn thật chút ít (không đếm lệnh `look`); mốc 100.000 yêu cầu/ngày của Durable Object, hết lúc 0 giờ UTC | ước tính "9 giờ ngắm cơ/ngày" của Chặng 2 nay có số thật để so |
| Khoá | `ADMIN_KEY` (bí mật của Worker, `wrangler secret put`); `status` đòi `key`, sai hoặc chưa đặt → 403. `health` không cần khoá, chỉ lộ số phòng và % | người lạ không xem được mã phòng và nhật ký; UptimeRobot cần gọi không khoá |
| Khoá ở máy bạn | `NEONPOOL_ADMIN_KEY`, hoặc file `%APPDATA%\NeonPool\relay-admin.key` (ngoài git) | công cụ đọc tự động |
| Hai bản | `server/local_relay.py` làm y hệt (khoá = tham số `admin_key`, mức = `daily_limit`) | luật Chặng 2: hai bản không lệch; bộ test chạy trên cả hai |
| Đưa lên | lệnh `deploy` có sẵn nhưng Claude KHÔNG chạy khi chưa được nói (CLAUDE.md: deploy chỉ khi người dùng nói) | |

## Task (mỗi task một commit)
1. Tài liệu (commit này): brief, ARCHITECTURE (giao thức), GAME_DESIGN lần 23, PROGRESS.
2. `local_relay.py`: nhật ký, số liệu, `health`, `status`, `stat` + `HostRoom.report_rtt` / `Session` báo ping + test AC24–AC27.
3. `server/cloudflare/`: `Hub`, báo sổ, `health`, `status`, `stat` + cùng bộ test trên `wrangler dev` (AC28).
4. `tools/relay_ops.py` (`status`, `deploy`, `setup`) + test phần định dạng.
5. PROGRESS, cổng đầy đủ.

## Tiêu chí chấp nhận → test
| # | Tiêu chí | Test |
|---|---|---|
| AC24 | `status` đúng khoá: liệt kê phòng với trạng thái đúng (chờ → chơi → chủ mất kết nối) và tuổi; sai khoá / chưa đặt khoá = 403, không lộ gì | `test_ac24_*` trong `tests/test_net_ops.py` |
| AC25 | nhật ký ghi đúng thứ tự + lý do cho: phòng mới, khách vào, khách ra, chủ ra, chủ vào lại, chủ đóng, phòng bỏ quên (`idle`), hết hạn (`expired`), khách bị thay; tối đa 200 dòng | `test_ac25_*` |
| AC26 | số hôm nay đếm đúng phòng mới, lượt vào, khung; `health` 200 → 503 khi vượt 90% mức; sang ngày UTC mới thì về 0 | `test_ac26_*` |
| AC27 | chủ phòng khai ping → `status` hiện đúng; chưa khai thì `null`; khách chưa vào thì bỏ qua; `Session` thật qua máy trung chuyển khai được | `test_ac27_*` |
| AC28 | cùng bộ test (AC24–AC27, trừ chỗ cần đồng hồ ngắn) xanh trên bản Cloudflare chạy máy mình | `NEONPOOL_RELAY_TEST_URL=... pytest tests/test_net_ops.py` |
| AC29 | `relay_ops` dựng bảng từ JSON `status` (có/không phòng, nhật ký trống, mã lạ), đọc khoá từ biến môi trường rồi từ file, báo rõ khi thiếu khoá | `tests/test_relay_ops.py` |
