# NeonPool — kiến trúc và hợp đồng module

Nguồn sự thật cho cách code. Cần thứ chưa có ở đây → thêm TRONG file mình sở hữu và ghi vào đây; không đổi chữ ký công khai của module khác.

## Chạy / công cụ
- Python: `.venv\Scripts\python.exe` (3.13), pygame-ce 2.5.8 (`import pygame as pg`), numpy có sẵn, pytest, ruff.
- Chạy game: `.venv\Scripts\python.exe main.py` · không cửa sổ: đặt `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` (tools và tests tự đặt).
- Chú thích code bằng tiếng Anh, ngắn. Type hint cho hàm công khai. Không `print` trong vòng lặp nóng; dùng `logging` (logger `neonpool`).

## Bố cục thư mục
```
main.py                  # from game.app import App; App.run_forever()
game/
  config.py              # hằng số + bộ thông số có tên (PHYSICS_DT, PX_PER_M, BALL_R, TABLE_*, FEEL_SETS)
  i18n.py                # t("khoa"), set_lang("vi"|"en"); đọc lang/*.json (utf-8)
  app.py                 # App: vòng lặp + chuyển cảnh
  physics/               # THUẦN, không import pygame
    shot.py              #   Shot(angle, power, spin)
    world.py             #   World.step(dt) -> list[Event]; trạng thái bi (+ "kho xoáy" qx, qy của bi trắng); rng riêng
    collide.py           #   bi–bi, bi–băng, bi–lỗ
  rules/                 # THUẦN: eight_ball.py nhận Event -> trạng thái ván (nhóm, lỗi, thắng/thua, `score`: thắng = 1000 − 10/cú − 50/lỗi, tối thiểu 100; thua = 50/bi đã vào, không tính bi 8; hằng số `SCORE_*` ở config.py)
  tally.py               # THUẦN: `Tally` = đồng hồ cho số ở thẻ kết quả đếm lên (điểm → số cú → lỗi): `value`, `ticks_done`, `tick_pitch`, `flash`, `finished` theo tuổi thẻ; thẻ vẽ và PlayScene phát tiếng tích/ting từ cùng một nguồn; hằng số `TALLY_*` ở config.py
  music.py               # THUẦN (numpy, không pygame): `Style` (nhịp, hợp âm, mức từng lớp: pad, arp, bass, kick, hat, bell) + `render(style)` -> một vòng lặp int16 liền mạch (đuôi cuối vòng cuộn về đầu); 4 style có tên, `TRACKS` = bài đang dùng cho "menu" và "play"
  input/                 # drag.py: Knob (cơ như núm vặn quanh bi trắng) + DragAim (kéo ngược hướng muốn đánh: hướng và lực đều theo hướng kéo, tính từ chỗ bấm) -> trả Shot; cách nhập nào thêm sau này cũng chỉ trả Shot
  settings.py            # cài đặt của người chơi (ngôn ngữ, âm lượng, âm lượng nhạc, rung, FPS): JSON trong %APPDATA%\NeonPool, biến NEONPOOL_SETTINGS đổi chỗ (test và tools dùng); thuần, không pygame
  render/                # vẽ: bàn tối giản (table.py), bi (+ `SpinBalls`: bi xoay số/vạch sọc, mỗi 3° một sprite) + cơ neon + nút đặc (draw.py), chữ + số 7 đoạn + bảng điểm + hình bi xoáy (hud.py), nền synthwave + sóng sống + bi trôi ở menu (synth.py), vệt quét CRT (crt.py), ánh sáng (glow.py), vòng sóng (fx.py), phông (fonts.py: assets/fonts, OFL), màu (palette.py); PX_PER_M chỉ dùng ở đây
  render/frozen.py       # `FrozenScene`: ảnh cảnh phía sau một bảng nổi (chụp khung đầu, rồi dán; khi bảng mở yên thì nền tối + khung bảng được nướng MỘT lần) — Hướng dẫn và Cài đặt dùng chung; `draw.veil(size, alpha)` là lớp phủ tối có đệm
  scenes/                # menu, play, help (`HelpPanel`: carousel NỔI do App giữ, vẽ đè lên menu hoặc bàn; + help_pictures: ảnh thật chụp từ PlayScene), settings (bảng Cài đặt nổi trên menu)
lang/vi.json, en.json
tests/                   # pytest; conftest.py đặt SDL dummy
tools/                   # gate.py (cổng), smoke.py, shot.py, _out/ (git bỏ qua)
```

## Hợp đồng chính
- `Shot(angle: float, power: float 0..1, spin: float -1..1)`: spin = cao(+)/thấp(−) trên bi trắng. Ngoài `Shot`, không có đường nào khác để tác động bi trắng. Vật lý DÙNG spin từ 2026-10-30: `World.apply` cho bi trắng một "kho xoáy" q = spin · min(`base` + `gain` · tốc độ, `SPIN_MAX_RATIO` · tốc độ) dọc đường ngắm; mỗi bước con `_slide` dùng q dần (`decay` m/s²) và cộng `SLIDE_GAIN` (2/7) đơn vị tốc độ dọc q cho mỗi đơn vị q đã dùng (cao: bi chạy tiếp; thấp: lùi). q không đổi khi va chạm hay đụng băng, về 0 khi đặt bi (`place`, `rack`) hoặc rơi lỗ. Bi có q chưa được coi là dừng (`at_rest`, và không bị "dừng cứng" `REST_SPEED`). spin 0 không chạm tới q: kết quả y hệt trước. Bộ thông số có tên ở `config.SPIN_SETS` (NHE/VUA/MANH), `World(spin=SpinSet)`.
- `World(seed, feel, rack=True, spin=None)`; `balls[n].number == n` (0 = bi trắng, 1–15); `World.place(n, x, y, vx, vy)`, `respawn_cue()`, `can_place_cue(x, y)`, `place_cue(x, y)` (bi trắng trong tay: trong bàn, không đè bi, ngoài miệng lỗ), `apply(shot)`, `step() -> list[Event]`, `at_rest()`, `kinetic_energy()`. `step()` luôn tiến đúng `PHYSICS_DT` (bên trong chia bước con chống xuyên); App gom dt khung hình thành nhiều bước (trần `MAX_FRAME_DT` = 0,05 s để khỏi "xoắn ốc chết"). Chồng lấn bi còn lại ≤ ~4 µm nhờ lặp tách bi tối đa 16 lượt.
- `Event`: `BallHitBall(a, b, speed)`, `BallHitCushion(ball, speed)`, `BallPocketed(ball, pocket)`; `speed` = vận tốc va theo pháp tuyến (m/s), phát mọi va chạm có tốc độ > `MIN_EVENT_SPEED` (0,001 m/s: luật cần cả cú chạm rất nhẹ); `Audio` tự bỏ tiếng nhỏ hơn `SFX_MIN_SPEED`. `rules` chỉ đọc Event, không đọc trạng thái vật lý.
- `physics.first_contact(balls, origin, direction) -> Contact(kind, distance, point, ball, object_dir)`: điểm bi trắng chạm đầu tiên (bi hoặc băng) cho vạch ngắm.
- `rules.eight_ball.EightBall` (thay `FreePlay`; xem docs/plans/20261028-8ball.md): `on_shot()`, `on_events(events)`, `finish_shot() -> ShotResult` (gọi khi mọi bi đã dừng: xét lỗi, chọn nhóm, thắng/thua), `cue_placed()`, `rerack()`, `reset()`; `shots, fouls, pocketed, group (None|'solid'|'stripe'), phase ('playing'|'won'|'lost'), cue_in_hand, is_break, balls_left`, `group_left()`, `eight_is_next()`. `ShotResult.outcome` ∈ {None, WON, LOST, RERACK}; lỗi là khoá `foul.*`. `PlayScene` giữ vòng đời: `fire()` → bi chạy → dừng → `finish_shot()` → thông báo / đặt bi trắng / bảng kết quả.
- `App`: `__init__(screen)`, `prepare()` (game thật gọi MỘT lần trước khung đầu, sau màn chờ `_show_loading`: dựng sẵn mọi hình Hướng dẫn, bảng Cài đặt, thẻ kết quả, ~0,9 s ở 1080p / ~1,2 s ở 1440p; về sau, khi đổi ngôn ngữ hay cỡ cửa sổ, menu rảnh 1,5 s thì dựng lại như cũ), `handle_event(e)`, `update(dt)`, `draw()`, `go_play()`, `go_menu()`, `open_help()` (H trong ván, nút ở menu: mở `app.help` đè lên cảnh hiện tại, Esc/H/✕ đóng; khi mở, App chuyển hết phím/chuột cho nó và bàn chơi tạm dừng phía sau; cảnh phía sau, menu hay bàn, là ảnh đóng băng `FrozenScene` khi khung đã mở yên) — tools/smoke.py và tools/shot.py dựa vào các hàm này. App mở ở menu; `PlayScene` được giữ sống để Esc → menu → "Chơi tiếp" vẫn đúng ván cũ. Phím toàn cục (App): F11 toàn màn hình, M tắt/mở tiếng; phím riêng của bàn (R, 1/2/3, H, Esc) nằm ở `PlayScene`. Xoáy trong `PlayScene`: `spin` (−1..1, nấc 1/32, giữa dễ trúng), `_dial_event` (bấm/kéo chấm ở `hud.SPIN_C`, con lăn `SPIN_WHEEL_STEP`; chỉ khi mọi bi đứng yên), `DragAim.end(spin)` đặt xoáy vào `Shot`, `new_game` đưa về giữa còn `fire` giữ nguyên (lần 13); mỗi lần qua một nấc (1/4) hoặc bấm vào hình, `Audio.play_spin(level)` kêu một tiếng "cộc" trầm, cao độ theo mức (`SPIN_SOUNDS`: ba bản TRAM / VUA / SANG, 330–932 Hz, cùng độ to, chờ người dùng nghe chọn; `NEONPOOL_SPIN_SOUND` chọn bản khi chơi thử, `tools/spin_sound_preview.py` ghi WAV); biến môi trường `NEONPOOL_SPIN_SET` chọn bộ `SPIN_SETS` để chơi thử (xoá khi đã chọn).
- Vẽ: mã game và layout dùng đơn vị LOGIC (1280×720, "khung"); chỉ lúc vẽ mới nhân với `View.s` và cộng độ lệch khung (`View.ox, oy`) để ra pixel thật. Canvas là CẢ CỬA SỔ (`View.canvas`), khung nằm giữa đúng tỉ lệ, cảnh nào cũng tô nền tới bốn mép; thường cảnh vẽ thẳng lên màn hình (chỉ khi rung hoặc đang đổi cỡ mới qua canvas phụ). Ảnh Hướng dẫn dùng `View.framed()` (không lệch). Game mở toàn màn hình; F11 đổi qua lại. Khi đổi cỡ cửa sổ, App chờ `RESIZE_SETTLE_S` rồi gọi `set_view` cho từng scene để dựng lại bàn/bi đúng độ phân giải (trong lúc chờ chỉ kéo giãn tạm). Hình mịn: vẽ lớn (`View.scaled(k)`) rồi thu bằng `shrink_pm`/`Aa`.
- Chuột: App đổi toạ độ cửa sổ → toạ độ canvas logic 1280×720 (`render/viewport.py`) TRƯỚC khi giao cho scene; scene chỉ biết toạ độ logic.
- `i18n.t("khoa")`: `lang/vi.json` và `lang/en.json` phải cùng bộ khoá (test); khoá thiếu → thử ngôn ngữ kia → trả chính khoá + log cảnh báo. `render/fonts.get(size, bold)` tự tạo lại phông nếu pygame đã tắt/bật lại.
- `Audio` (`game/audio.py`): tổng hợp âm bằng numpy, không có thiết bị thì im lặng; NHẠC: `update_music(dt, track, duck)` mỗi khung (App gọi: "menu" khi đang ở menu, còn lại "play"; `duck` khi thẻ kết quả hiện) — hai bài lặp vô hạn, mỗi bài một kênh mixer dành riêng (`MUSIC_CHANNELS`, tiếng hiệu ứng không bao giờ lấy), chéo mờ `MUSIC_FADE_S`, âm lượng riêng `music_volume`, M tắt cả nhạc; bài được tạo bằng một luồng nền ở lần gọi đầu (biến môi trường `NEONPOOL_NO_MUSIC` tắt: test và tools đặt sẵn); `on_events` chỉ phát tối đa `SFX_MAX_PER_FRAME` tiếng mạnh nhất mỗi khung (tiếng rơi lỗ luôn được phát). `Fx` (`render/fx.py`): vòng sóng ánh sáng (màu và độ lan theo loại: bi, băng, lỗ), bi co vào lỗ, rung — chỉ phụ thuộc thời gian, không ngẫu nhiên.
- Neon (ánh sáng): mọi thứ sáng là hình premultiplied + quầng từ `render/glow.py` (`halo`, `lit`; làm mờ bằng thu rồi phóng, KHÔNG dùng `pg.transform.gaussian_blur` vì chậm ~500 ms/lớp lớn). Cộng sáng lên nền tối bằng `BLEND_RGB_ADD` (`draw.blit_add`): dải sóng (`waves.Waves`: dựng sẵn một lần rồi chỉ cuộn), sóng lan bàn khi bi rơi lỗ (`fx.Fx` vẽ lên một lớp cỡ bàn, chỉ khi có sóng), chữ phát sáng (`hud.glow_text`). Mức sáng đọc từ `palette.LOOK` lúc dựng. `table.build_table(v)` được nhớ theo độ phân giải (màn Hướng dẫn dùng chung bàn với ván): KHÔNG vẽ lên kết quả, chỉ blit. `view.CropView` cho lớp vẽ lớn chỉ rộng bằng bàn. Đồng hồ hiệu ứng là `_clock` của scene (không phải đồng hồ máy), nên ảnh chụp lặp lại được.

## Thành phần UI dùng chung (một chức năng, một thành phần — luật: `workflow/ui.md` 4d)
Thêm dòng khi tạo thành phần chung mới. "Khác có chủ ý" chỉ ghi điểm người dùng đã chốt cho khác (kèm lý do); điểm không ghi ở đó thì PHẢI giống. "Chưa gom" là nợ: gom khi chạm tới, nếu việc gom không đổi thứ người chơi thấy.

| Chức năng | Thành phần chung | Dùng ở | Khác có chủ ý |
|---|---|---|---|
| Nút chữ có hiệu ứng (rê, bấm, chọn, nút chính) | `hud.live_button` + `hud.ButtonFx`, khung trượt `hud.glide_frame` | Menu, nút Xong ở Cài đặt, thẻ kết quả | — |
| Dấu ▶ nhỏ trên nút đang chọn | `hud.arrow` | mọi nút chữ | — |
| Chỉnh mức xoáy bằng chấm kéo + con lăn chuột | `hud.spin_dial` + `hud.spin_value` (vị trí `hud.SPIN_C`, bán kính `SPIN_R`) | bảng bên của ván chơi (và hình trang Phím tắt của Hướng dẫn) | — |
| Bảng / thẻ nổi trên cảnh đóng băng | `render/frozen.FrozenScene` + `draw.veil` | Hướng dẫn, Cài đặt, thẻ kết quả | Cài đặt đóng bằng nút Xong, không có ✕ như Hướng dẫn (người dùng chốt 2026-10-30: không cần) |

Chưa gom (kiểm lần cuối 2026-10-30, đọc code; người dùng chốt 2026-10-30: chưa cần sửa các mục này, chỉ gom khi chạm tới và việc gom không đổi hình):
- Mũi tên "bước trước/sau": Hướng dẫn dùng `help._arrow_button` + `_chevron` (nút tròn viền sáng, chữ V nét, nhún khi bấm); Cài đặt dùng `settings._chooser` + `_triangle` (tam giác đặc, không có nút tròn). Cùng chức năng, hai kiểu. `settings._triangle` còn là bản chép của `hud.arrow` có thêm hướng.
- Nút phụ phình/nhún: `help._arrow_button` và `help._close_button` tự lặp công thức sáng/nhấn/phình (`lit`, `press_k`, `grow`) ngoài `live_button`.
## Quy ước chống lỗi (chi tiết kiểm thử: workflow/physics.md)
- Bi tốc độ cao có thể xuyên băng/xuyên bi giữa hai bước: bước cố định nhỏ + chia bước con theo vận tốc tối đa, hoặc phát hiện va chạm liên tục. Không dựa vào "tốc độ chắc không tới mức đó".
- Bi gần dừng: ngưỡng dừng cứng (`REST_SPEED`) để khỏi rung vô hạn.
- Thứ tự giải va chạm nhiều bi cùng lúc phải xác định (sắp theo chỉ số bi), không phụ thuộc thứ tự dict/set.

- App: đổi cảnh qua `_switch` (hiệu ứng tắt/bật TV CRT, ~0,34 s, chỉ là hình: cảnh đổi NGAY, tools gọi `skip_transition()` để chụp). `App.change_settings(**)` áp và lưu cài đặt. Chữ: `hud.text` đặt theo đường chân chữ đo từ đáy ô (phông nới ô ở phía trên khi chữ hoa có hai tầng dấu); không tự cộng trừ px.
