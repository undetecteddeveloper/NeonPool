# Đường: Dọn code / hiệu năng / test

Refactor, tách module, tăng tốc, viết thêm test, nâng thư viện. Mục tiêu: hành vi người chơi thấy KHÔNG đổi.

1. Trước khi đụng: có test (hoặc ảnh chụp `tools\shot.py` cố định + số đo `smoke.py`) bắt được hành vi hiện tại. Chưa có thì viết trước, commit riêng `test(scope): ...`.
2. Hiệu năng (đo ĐÚNG điều kiện game thật, ghi 2026-10-30 sau khi người dùng báo tụt FPS menu hai lần mà lần đầu tôi đo thiếu: bật `app.help.prefetch = True` như `run_forever`, KHÔNG đặt `NEONPOOL_NO_MUSIC` khi nghi luồng nhạc, chạy `app.update(1/60); app.draw()` với dt cố định và ghi thời gian vẽ từng khung theo THỜI ĐIỂM; một chi phí thật rơi đúng cùng khung ở mọi lần chạy, còn khung lẻ không lặp là nhiễu máy. Không tin FPS đo qua `clock.tick` ở máy không cửa sổ: nó dao động 60 ↔ 38). ĐO trước khi sửa (`smoke.py` ms/khung; cần chi tiết thì `cProfile` trên `smoke`), ghi số vào PROGRESS.md, sửa chỗ nóng nhất, đo lại. Không tối ưu theo cảm giác. Mục tiêu 60 FPS (≤ 16 ms/khung).
3. Mỗi commit một thay đổi (một lần chuyển file, một lần đổi tên) để `git bisect` được. Không trộn refactor với đổi hành vi.
4. Tách module phải giữ bất biến §1 (physics/rules không import pygame) và hợp đồng ARCHITECTURE.md; đổi hợp đồng thì sửa tài liệu cùng commit. Gom các bản vẽ riêng của cùng một chức năng UI về một thành phần chung (cột "Chưa gom" trong ARCHITECTURE.md): làm theo `ui.md` 4d; ảnh chụp trước/sau của mỗi màn phải giống hệt nếu hai bản vốn đã giống, còn nếu hình đổi thì đó là việc giao diện, hỏi (CLAUDE.md §1b).
5. Nâng thư viện: sửa `requirements.txt` + cài trong `.venv`, chạy cổng đầy đủ. Test vật lý đổi kết quả sau nâng cấp = dừng và báo.
6. Kết thúc: `gate.py` đầy đủ; commit `refactor/perf/test(scope): ...`; báo cáo dòng đầu `ĐỦ BƯỚC` / `THIẾU …` với số đo trước/sau.
