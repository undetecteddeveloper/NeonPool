# Đường: Tính năng

Có giao diện → đọc thêm `ui.md`. Đụng va chạm/xoáy/ma sát → đọc thêm `physics.md`.

1. Hỏi hướng SẢN PHẨM trước (CLAUDE.md §1b): chỉ chỗ có ≥2 hướng người chơi thấy khác nhau. Kỹ thuật tự quyết.
2. Tài liệu theo độ lớn — viết vừa đủ để code, GIỮ tiêu chí chấp nhận đánh số, bảng quyết định, chữ ký hàm, danh sách file, bước kiểm; BỎ nền, so sánh, đoạn mô tả lại code có sẵn:
   - **Nhỏ** (vài file, không đổi hành vi người chơi thấy): không tài liệu, làm như việc vặt nhưng chạy đủ cổng.
   - **Vừa**: một brief ≤100 dòng ở `docs/plans/<yyyymmdd>-<slug>.md` (yêu cầu + quyết định + danh sách task). Có đổi mục nào trong `GAME_DESIGN.md` thì sửa file đó cùng commit.
   - **Lớn** (nhiều module, đổi hợp đồng ở ARCHITECTURE.md): brief như trên + tách task, mỗi task một commit. Đổi hợp đồng thì sửa ARCHITECTURE.md TRƯỚC khi code.
3. Test đi cùng code: logic thuần (`physics/`, `rules/`) viết test trước hoặc cùng lúc; tiêu chí chấp nhận nào kiểm bằng máy được thì phải có test mang tên tiêu chí đó.
4. Mở rộng thứ có sẵn: đọc code hiện tại và hợp đồng trong ARCHITECTURE.md trước; thêm đường mới vào `Shot`/`Event` thì sửa mọi nơi tiêu thụ (Grep) cùng đợt.
5. Chuỗi mới hiện ra màn hình: thêm vào CẢ `lang/vi.json` và `lang/en.json` cùng commit.
6. Kết thúc: `gate.py` đầy đủ (exit code thật); cập nhật PROGRESS.md (số đo + lý do + việc còn lại); commit `feat(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …`. Tính năng người chơi thấy được: chụp ảnh bằng `tools\shot.py` và nhìn ảnh trước khi báo.
