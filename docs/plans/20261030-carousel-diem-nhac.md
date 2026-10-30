# Brief — điểm, hướng dẫn carousel, nhạc nền (2026-10-30)

Nội dung người chơi thấy: `GAME_DESIGN.md` "Phản hồi lần 10". Brief này chỉ chốt cách làm và tiêu chí kiểm.

## Tiêu chí chấp nhận (mỗi dòng có test mang tên tương ứng)
**Điểm** (`tests/test_eight_ball.py`, `tests/test_play_rules.py`)
- AC1 Thắng: điểm = 1000 − 10·cú − 50·lỗi, tối thiểu 100. 22 cú + 6 lỗi = 480.
- AC2 Thua (và ván đang chơi): 50 điểm cho mỗi bi đã vào lỗ, bi 8 không tính.
- AC3 Thẻ kết quả vẽ dòng điểm dưới tiêu đề ở vi và en; mọi nút và hàng nằm trong thẻ, hàng cuối cao hơn nút.

**Hướng dẫn carousel** (`tests/test_help.py`, chạy trên cả hai bố cục)
- AC4 Nút menu và phím H mở khung ĐÈ lên cảnh đang có; không đổi cảnh. Esc, H, ✕, bấm ra ngoài khung đều đóng; bấm trong khung thì không.
- AC5 Khi khung mở, cảnh phía sau không nhận phím/chuột; bàn chơi đứng yên, đóng xong chạy tiếp đúng chỗ. Mở khung huỷ cú ngắm đang dở.
- AC6 Mũi tên, ← →, chấm trang đều lật; lật vòng tròn ở hai đầu; khung nhớ trang đang xem.
- AC7 Mở = vệt sáng ngang rồi bung ra (kiểm bằng độ sáng điểm ảnh). Lật trang (lần 11) = trượt + mờ theo hướng bấm: `flip_state` (hai độ mờ cộng lại bằng 1, đối xứng theo hướng), hướng đúng với mũi tên/phím/chấm, trang không tràn ra ngoài chỗ của nó.
- AC8 Chữ mọi chủ đề vi + en không tràn cột và nằm trong vùng nội dung; khung và nút nằm trong màn hình.
- AC9 Hình dựng sẵn đúng cỡ hiển thị (`help_pictures.build(i, View(k))`), không phóng.

**Nhạc** (`tests/test_music.py`, `tests/test_settings_and_controls.py`)
- AC10 Mỗi style tạo ra vòng lặp int16 mono đúng độ dài, to bằng nhau (RMS), không méo, đầu nối đuôi không có bước nhảy lớn hơn bước thường, cùng style cùng mẫu.
- AC11 Menu phát bài menu, bàn phát bài bàn; chéo mờ `MUSIC_FADE_S`; hộp hướng dẫn và Cài đặt giữ nguyên nhạc đang phát.
- AC12 Nhạc có âm lượng riêng (`Settings.music`, lưu cùng cài đặt, thanh "Nhạc nền" kéo và bấm được); M tắt cả nhạc; thẻ kết quả hạ nhạc còn `MUSIC_DUCK`.
- AC13 Hiệu ứng không bao giờ lấy kênh của nhạc; không có thiết bị âm thanh hoặc `NEONPOOL_NO_MUSIC` thì game vẫn chạy.

## Quyết định kỹ thuật (đã nói lý do)
| Chỗ | Chọn | Vì |
|---|---|---|
| Khung hướng dẫn | `HelpPanel` do `App` giữ, vẽ sau cảnh, không phải `Scene` | đè lên cả menu lẫn bàn mà không sửa hai cảnh; `App` chặn phím/chuột và tạm dừng bàn |
| Mở/đóng | cắt (`set_clip`) một dải quanh vạch giữa, dải lớn dần | vẽ thẳng ở độ phân giải thật, không phóng, rẻ |
| Lật trang | hai bề mặt đặc của trang, mỗi bề mặt dán lệch ngang với độ mờ riêng, cắt trong chỗ của trang | trượt + mờ, người dùng chọn lần 11; không phóng, không co |
| Hình trong khung | dựng ở thang `View(s·k)` | nét như vẽ thật, không thu từ ảnh lớn |
| Nhạc | `music.render(Style)` bằng numpy, một luồng nền; mixer chỉ đụng ở luồng chính | không file nhạc, không bản quyền; 0,3–0,4 s mỗi bài |
| Kênh | `set_reserved(MUSIC_CHANNELS)` | hiệu ứng `Sound.play()` không bao giờ cướp kênh nhạc |

## Việc (mỗi việc một commit)
| # | Việc | File |
|---|---|---|
| T1 | Điểm: hằng số, `EightBall.score`, thẻ kết quả, chuỗi `result.score` | `config.py`, `rules/eight_ball.py`, `render/hud.py`, `lang/*` |
| T2 | Carousel: `HelpPanel`, `App.open_help`, bỏ màn Hướng dẫn riêng | `scenes/help.py`, `app.py`, `menu.py`, `play.py`, tools |
| T3 | Nhạc: `music.py`, `Audio.update_music`, `Settings.music`, hàng Cài đặt, `tools/music_preview.py` | `music.py`, `audio.py`, `settings.py`, `scenes/settings.py` |
| T4 | Tài liệu: GAME_DESIGN, ARCHITECTURE, PROGRESS | `docs/`, `PROGRESS.md` |

## Còn chờ người dùng
Chọn bố cục khung (`wide` / `inside`) sau khi xem ảnh; nghe `tools/_out/music/*.wav` và chọn một bản menu, một bản chơi. Bản không chọn bị xoá khỏi code.

## Bổ sung lần 11 (2026-10-30)
**Số chạy ở thẻ kết quả** (`tests/test_tally.py`)
- AC14 `Tally`: số đếm lên từ 0, chỉ tăng, chậm dần, dừng đúng ở giá trị cuối; thứ tự điểm → số cú → lỗi cách nhau `TALLY_GAP_S`; trước `TALLY_START_S` mọi số là 0.
- AC15 Tiếng tích: tối đa `TALLY_MAX_TICKS` mỗi số (ít hơn khi số nhỏ), thưa dần, cao độ chỉ đi lên; số 0 im lặng. Tiếng ting khi số dừng: sáng khi thắng, trầm khi thua, của điểm to nhất.
- AC16 Số vừa dừng loé sáng `TALLY_FLASH_S`; nút Chơi ván mới dùng được ngay khi đang đếm; thẻ không đếm (ảnh hướng dẫn) vẽ số đủ; bàn chơi tạm dừng thì đếm cũng dừng.

**Nhạc lúc chơi** (`tests/test_music.py`)
- AC17 Ba bản `play_*` đều ≥ 98 BPM, có kick, bass nhịp tám và hi-hat; bản đang dùng có kick; `play_bounce` có thêm vỗ tay.

**Lỗi FPS khi mở Cài đặt** (`tests/test_neon.py`, `tests/test_settings_and_controls.py`)
- AC18 Mở Cài đặt chỉ dựng MỘT sprite khung bảng, không phải mỗi khung; quầng sáng làm tròn theo 1/8; kho đệm sprite bỏ 1/3 mục cũ nhất khi đầy chứ không xoá cả kho; bảng được dựng sẵn khi menu rảnh (game thật).
- AC19 Bảng Cài đặt mở yên thì menu phía sau không bị vẽ lại mỗi khung; đang đóng thì menu vẽ thật.
