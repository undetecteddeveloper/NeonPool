# Đường: Dọn code / hiệu năng / test

Refactor, tách module, tăng tốc, viết thêm test, nâng thư viện. Mục tiêu: hành vi người chơi thấy KHÔNG đổi.

1. Trước khi đụng: có test (hoặc ảnh chụp `tools\shot.py` cố định + số đo `smoke.py`) bắt được hành vi hiện tại. Chưa có thì viết trước, commit riêng `test(scope): ...`.
2. Hiệu năng: ĐO trước khi sửa (`smoke.py` ms/khung; cần chi tiết thì `cProfile` trên `smoke`), ghi số vào PROGRESS.md, sửa chỗ nóng nhất, đo lại. Không tối ưu theo cảm giác. Mục tiêu 60 FPS (≤ 16 ms/khung).
3. Mỗi commit một thay đổi (một lần chuyển file, một lần đổi tên) để `git bisect` được. Không trộn refactor với đổi hành vi.
4. Tách module phải giữ bất biến §1 (physics/rules không import pygame) và hợp đồng ARCHITECTURE.md; đổi hợp đồng thì sửa tài liệu cùng commit. Gom các bản vẽ riêng của cùng một chức năng UI về một thành phần chung (cột "Chưa gom" trong ARCHITECTURE.md): làm theo `ui.md` 4d; ảnh chụp trước/sau của mỗi màn phải giống hệt nếu hai bản vốn đã giống, còn nếu hình đổi thì đó là việc giao diện, hỏi (CLAUDE.md §1b).
5. Nâng thư viện: sửa `requirements.txt` + cài trong `.venv`, chạy cổng đầy đủ. Test vật lý đổi kết quả sau nâng cấp = dừng và báo.
6. Kết thúc: `gate.py` đầy đủ; commit `refactor/perf/test(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …` với số đo trước/sau.
