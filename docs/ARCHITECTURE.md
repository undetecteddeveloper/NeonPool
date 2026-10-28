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
- `World(seed)`, `World.place(balls)`, `World.apply(shot)`, `World.step(dt) -> list[Event]`, `World.at_rest() -> bool`. `step` chỉ nhận `PHYSICS_DT`; App gom dt khung hình thành nhiều bước cố định (trần dt 0,05 s để khỏi "xoắn ốc chết").
- `Event`: `BallHitBall(a, b)`, `BallHitCushion(ball)`, `BallPocketed(ball, pocket)`, `BallLeftTable(ball)`. `rules` chỉ đọc Event, không đọc trạng thái vật lý.
- `App`: `__init__(screen)`, `handle_event(e)`, `update(dt)`, `draw()` — tools/smoke.py và tools/shot.py dựa vào đúng bốn thứ này.

## Quy ước chống lỗi (chi tiết kiểm thử: workflow/physics.md)
- Bi tốc độ cao có thể xuyên băng/xuyên bi giữa hai bước: bước cố định nhỏ + chia bước con theo vận tốc tối đa, hoặc phát hiện va chạm liên tục. Không dựa vào "tốc độ chắc không tới mức đó".
- Bi gần dừng: ngưỡng dừng cứng (`REST_SPEED`) để khỏi rung vô hạn.
- Thứ tự giải va chạm nhiều bi cùng lúc phải xác định (sắp theo chỉ số bi), không phụ thuộc thứ tự dict/set.
