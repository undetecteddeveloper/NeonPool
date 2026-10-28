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
  render/                # vẽ bàn (table.py), bi, thanh kéo, HUD; PX_PER_M chỉ dùng ở đây
  scenes/                # menu, play, ...
lang/vi.json, en.json
tests/                   # pytest; conftest.py đặt SDL dummy
tools/                   # gate.py (cổng), smoke.py, shot.py, _out/ (git bỏ qua)
```

## Hợp đồng chính
- `Shot(angle: float, power: float 0..1, spin: float -1..1)`: spin = cao(+)/thấp(−) trên bi trắng. Ngoài `Shot`, không có đường nào khác để tác động bi trắng.
- `World(seed, feel, rack=True)`; `balls[n].number == n` (0 = bi trắng, 1–15); `World.place(n, x, y, vx, vy)`, `respawn_cue()`, `can_place_cue(x, y)`, `place_cue(x, y)` (bi trắng trong tay: trong bàn, không đè bi, ngoài miệng lỗ), `apply(shot)`, `step() -> list[Event]`, `at_rest()`, `kinetic_energy()`. `step()` luôn tiến đúng `PHYSICS_DT` (bên trong chia bước con chống xuyên); App gom dt khung hình thành nhiều bước (trần `MAX_FRAME_DT` = 0,05 s để khỏi "xoắn ốc chết"). Chồng lấn bi còn lại ≤ ~4 µm nhờ lặp tách bi tối đa 16 lượt.
- `Event`: `BallHitBall(a, b, speed)`, `BallHitCushion(ball, speed)`, `BallPocketed(ball, pocket)`; `speed` = vận tốc va theo pháp tuyến (m/s), phát mọi va chạm có tốc độ > `MIN_EVENT_SPEED` (0,001 m/s: luật cần cả cú chạm rất nhẹ); `Audio` tự bỏ tiếng nhỏ hơn `SFX_MIN_SPEED`. `rules` chỉ đọc Event, không đọc trạng thái vật lý.
- `physics.first_contact(balls, origin, direction) -> Contact(kind, distance, point, ball, object_dir)`: điểm bi trắng chạm đầu tiên (bi hoặc băng) cho vạch ngắm.
- `rules.eight_ball.EightBall` (thay `FreePlay`; luật dùng chung hai chế độ, xem docs/plans/20261028-8ball.md): `on_shot()`, `on_events(events)`, `finish_shot() -> ShotResult` (gọi khi mọi bi đã dừng: xét lỗi, chọn nhóm, thắng/thua), `cue_placed()`, `rerack()`, `reset()`; `shots, fouls, pocketed, group (None|'solid'|'stripe'), phase ('playing'|'won'|'lost'), cue_in_hand, is_break, balls_left`, `group_left()`, `eight_is_next()`. `ShotResult.outcome` ∈ {None, WON, LOST, RERACK}; lỗi là khoá `foul.*`. `PlayScene` giữ vòng đời: `fire()` → bi chạy → dừng → `finish_shot()` → thông báo / đặt bi trắng / bảng kết quả. Mức toán: `config.LEVELS[key]` (`line_tol, snap, coords, hint`), `PlayScene.level`, đổi ở menu.
- `App`: `__init__(screen)`, `handle_event(e)`, `update(dt)`, `draw()`, `go_play()`, `go_menu()` — tools/smoke.py và tools/shot.py dựa vào các hàm này. App mở ở menu; `PlayScene` được giữ sống để Esc → menu → "Chơi tiếp" vẫn đúng ván cũ. Phím toàn cục (App): F11 toàn màn hình, M tắt/mở tiếng; phím riêng của bàn (R, G, 1/2/3, Esc) nằm ở `PlayScene`.
- Vẽ: mã game và layout dùng đơn vị LOGIC (1280×720); chỉ lúc vẽ mới nhân với `View.s` để ra pixel thật, và canvas của App có kích thước ĐÚNG khung hình trong cửa sổ (không phóng/thu). Khi đổi cỡ cửa sổ, App chờ `RESIZE_SETTLE_S` rồi gọi `set_view` cho từng scene để dựng lại bàn/bi/lưới đúng độ phân giải (trong lúc chờ chỉ kéo giãn tạm). Hình mịn: vẽ lớn (`View.scaled(k)`) rồi thu bằng `shrink_pm`/`Aa`.
- Chuột: App đổi toạ độ cửa sổ → toạ độ canvas logic 1280×720 (`render/viewport.py`) TRƯỚC khi giao cho scene; scene chỉ biết toạ độ logic.
- `i18n.t("khoa")`: `lang/vi.json` và `lang/en.json` phải cùng bộ khoá (test); khoá thiếu → thử ngôn ngữ kia → trả chính khoá + log cảnh báo. `render/fonts.get(size, bold)` tự tạo lại phông nếu pygame đã tắt/bật lại.
- `Audio` (`game/audio.py`): tổng hợp âm bằng numpy, không có thiết bị thì im lặng; `on_events` chỉ phát tối đa `SFX_MAX_PER_FRAME` tiếng mạnh nhất mỗi khung (tiếng rơi lỗ luôn được phát). `Fx` (`render/fx.py`): vòng gợn, bi co vào lỗ, rung — chỉ phụ thuộc thời gian, không ngẫu nhiên.

## Quy ước chống lỗi (chi tiết kiểm thử: workflow/physics.md)
- Bi tốc độ cao có thể xuyên băng/xuyên bi giữa hai bước: bước cố định nhỏ + chia bước con theo vận tốc tối đa, hoặc phát hiện va chạm liên tục. Không dựa vào "tốc độ chắc không tới mức đó".
- Bi gần dừng: ngưỡng dừng cứng (`REST_SPEED`) để khỏi rung vô hạn.
- Thứ tự giải va chạm nhiều bi cùng lúc phải xác định (sắp theo chỉ số bi), không phụ thuộc thứ tự dict/set.
