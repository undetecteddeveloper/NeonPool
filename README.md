# NeonPool

*Mỗi cú đánh một vệt sáng / Every shot leaves a glow*

Game bida 8 bi phong cách synthwave arcade thập niên 80, viết bằng Python và pygame-ce. Chơi một mình hoặc chơi đôi qua mạng bằng mã phòng 4 chữ, có xoáy cao/thấp, tiếng và nhạc nền tự tạo bằng mã (không dùng file âm thanh). Giao diện tiếng Việt và tiếng Anh.

## Chạy game

Cần Windows và Python 3.13.

```
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Kéo từ bi trắng ra sau để ngắm và lấy lực rồi thả để đánh; chuột lăn hoặc kéo chấm ở bảng bên để chỉnh xoáy; `H` mở hướng dẫn, `M` tắt tiếng, `F11` đổi toàn màn hình / cửa sổ.

## Bản exe

```
.venv\Scripts\python.exe tools\build_exe.py
```

Ra `dist\NeonPool.exe` (một file, đã gói sẵn font và chữ). Thêm `--folder` nếu muốn thư mục khởi động nhanh hơn.

## Kiểm tra code

```
.venv\Scripts\python.exe tools\gate.py
```

Chạy ruff, pytest và đo ms/khung hình. Thiết kế: `docs/GAME_DESIGN.md`, kiến trúc: `docs/ARCHITECTURE.md`.

## Giấy phép

Chưa chọn giấy phép cho mã nguồn. Font Chakra Petch và Tilt Neon theo SIL Open Font License (xem `assets/fonts/`).
