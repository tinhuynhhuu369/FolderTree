# Folder Tree Viewer

Ứng dụng desktop viết bằng Python để vẽ cấu trúc cây của một thư mục: bạn nhập đường dẫn, app hiển thị toàn bộ thư mục con và file bên trong dưới dạng cây.

![Python](https://img.shields.io/badge/python-3.8%2B-blue) ![GUI](https://img.shields.io/badge/GUI-tkinter-green)

## Tính năng

- **Cây thư mục tương tác**: icon thư mục/file, mở/thu gọn từng nhánh, cột dung lượng và số mục bên trong.
- **Cây dạng văn bản** (giống lệnh `tree`), có thể copy hoặc lưu ra file `.txt`.
- **Tùy chọn quét**: giới hạn độ sâu, hiện/ẩn file ẩn, bỏ qua thư mục/file theo mẫu (`*.log`, `node_modules`, ...).
- **Thao tác trên file**: double-click để mở file, chuột phải để mở trong Explorer hoặc copy đường dẫn.
- **Chạy tốt với thư mục lớn**: quét ở luồng nền (không treo cửa sổ), có nút **Dừng**, cây chỉ nạp nhánh khi được mở.
- Thư mục không có quyền truy cập được tô đỏ kèm thông báo lỗi, không làm app crash.

## Hướng dẫn sử dụng

1. Nhập đường dẫn vào ô **Thư mục** hoặc bấm **Chọn...** để duyệt.
2. Bấm **Vẽ cây** (hoặc nhấn `Enter`). Trong lúc quét, nút đổi thành **Dừng** để ngắt giữa chừng.
3. Xem kết quả ở hai tab:
   - **Cây thư mục**: dùng **Mở rộng tất cả** / **Thu gọn tất cả** để xem nhanh.
   - **Dạng văn bản**: bấm **Copy** hoặc **Lưu ra file .txt**.
4. Thanh trạng thái phía dưới hiển thị tổng số thư mục, số file và tổng dung lượng.

### Các tùy chọn

| Tùy chọn | Mô tả |
|---|---|
| Độ sâu tối đa | `0` = quét toàn bộ. Thư mục bị cắt do giới hạn độ sâu có dấu `[...]` |
| Hiện file ẩn | Hiện file/thư mục bắt đầu bằng `.` hoặc có thuộc tính Hidden (mặc định tắt) |
| Hiện dung lượng | Bật/tắt dung lượng trong cây dạng văn bản |
| Bỏ qua | Danh sách mẫu tên, cách nhau bằng dấu phẩy, hỗ trợ ký tự đại diện `*` `?`. Mặc định: `.git, __pycache__, node_modules, .venv, .idea, .vs` |

### Ví dụ kết quả dạng văn bản

```
demo/  (14 B)
├── docs/  (2 B)
│   └── guide.md  (2 B)
├── src/  (5 B)
│   ├── utils/  (2 B)
│   │   └── helper.py  (2 B)
│   └── main.py  (3 B)
└── README.md  (7 B)
```

## Lưu ý

- Dung lượng thư mục là tổng dung lượng các file **đã được quét**. Khi đặt giới hạn độ sâu hoặc bỏ qua một số mục, con số này sẽ nhỏ hơn dung lượng thực tế.
- Symlink/junction tới thư mục không được đi vào, để tránh vòng lặp vô hạn.