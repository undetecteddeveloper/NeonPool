# MathofPool — kiến trúc và hợp đồng module

Nguồn sự thật cho cách code. Cần thứ chưa có ở đây → thêm TRONG file mình sở hữu và ghi vào đây; không đổi chữ ký công khai của module khác.

## Chạy / công cụ
- Python: `.venv\Scripts\python.exe` (3.13), pygame-ce 2.5.8 (`import pygame as pg`), numpy có sẵn, pytest, ruff.
- Chạy game: `.venv\Scripts\python.exe main.py` · không cửa sổ: đặt `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` (tools và tests tự đặt).
- Chú thích code bằng tiếng Anh, ngắn. Type hint cho hàm công khai. Không `print` trong vòng lặp nóng; dùng `logging` (logger `mathofpool`).

## Bố cục thư mục
```
main.py                  # from game.app import App; App.run_forever()
game/
  config.py              # hằng số + bộ thông số có tên (PHYSICS_DT, PX_PER_M, BALL_R, TABLE_*, FEEL_SETS)
  i18n.py                # t("khoa"), set_lang("vi"|"en"); đọc lang/*.json (utf-8)
  app.py                 # App: vòng lặp + chuyển cảnh
  physics/               # THUẦN, không import pygame
    shot.py              #   Shot(angle, power, spin)
    world.py             #   World.step(dt) -> list[Event]; trạng thái bi; rng riêng
    collide.py           #   bi–bi, bi–băng, bi–lỗ
  rules/                 # THUẦN: eight_ball.py nhận Event -> trạng thái ván (nhóm, lỗi, thắng/thua)
  input/                 # drag.py (bản đầu) · formula.py (bản sau) -> đều trả Shot
  render/                # vẽ bàn, bi, gậy, HUD; PX_PER_M chỉ dùng ở đây
  scenes/                # menu, play, ...
lang/vi.json, en.json
tests/                   # pytest; conftest.py đặt SDL dummy
tools/                   # gate.py (cổng), smoke.py, shot.py, _out/ (git bỏ qua)
```

## Hợp đồng chính
- `Shot(angle: float, power: float 0..1, spin: float -1..1)`: spin = cao(+)/thấp(−) trên bi trắng. Ngoài `Shot`, không có đường nào khác để tác động bi trắng.
- `World(seed, feel, rack=True)`; `balls[n].number == n` (0 = bi trắng, 1–15); `World.place(n, x, y, vx, vy)`, `respawn_cue()`, `apply(shot)`, `step() -> list[Event]`, `at_rest()`, `kinetic_energy()`. `step()` luôn tiến đúng `PHYSICS_DT` (bên trong chia bước con chống xuyên); App gom dt khung hình thành nhiều bước (trần `MAX_FRAME_DT` = 0,05 s để khỏi "xoắn ốc chết"). Chồng lấn bi còn lại ≤ ~4 µm nhờ lặp tách bi tối đa 16 lượt.
- `Event`: `BallHitBall(a, b, speed)`, `BallHitCushion(ball, speed)`, `BallPocketed(ball, pocket)`; `speed` = vận tốc va theo pháp tuyến (m/s), chỉ phát khi > `MIN_EVENT_SPEED`. `rules` chỉ đọc Event, không đọc trạng thái vật lý.
- `physics.first_contact(balls, origin, direction) -> Contact(kind, distance, point, ball, object_dir)`: điểm bi trắng chạm đầu tiên (bi hoặc băng) cho vạch ngắm.
- `rules.free_play.FreePlay`: `on_shot()`, `on_events(events)`, `shots`, `balls_left`, `take_cue_respawn()`.
- `App`: `__init__(screen)`, `handle_event(e)`, `update(dt)`, `draw()` — tools/smoke.py và tools/shot.py dựa vào đúng bốn thứ này.

## Quy ước chống lỗi (chi tiết kiểm thử: workflow/physics.md)
- Bi tốc độ cao có thể xuyên băng/xuyên bi giữa hai bước: bước cố định nhỏ + chia bước con theo vận tốc tối đa, hoặc phát hiện va chạm liên tục. Không dựa vào "tốc độ chắc không tới mức đó".
- Bi gần dừng: ngưỡng dừng cứng (`REST_SPEED`) để khỏi rung vô hạn.
- Thứ tự giải va chạm nhiều bi cùng lúc phải xác định (sắp theo chỉ số bi), không phụ thuộc thứ tự dict/set.
