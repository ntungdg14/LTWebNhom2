## Mô tả thay đổi

<!-- Tóm tắt ngắn gọn: thay đổi gì, vì sao thay đổi. -->

## Loại thay đổi

- [ ] Sửa lỗi (bug fix)
- [ ] Tính năng mới
- [ ] Giao diện / CSS / HTML
- [ ] Python / Flask (route, blueprint, config)
- [ ] Tài liệu / CI / cấu hình
- [ ] Refactor (không đổi hành vi)

## Liên kết liên quan

<!-- Issue / PR / thiết kế tham khảo: Closes #... -->

## Ảnh chụp màn hình

<!-- Bắt buộc với thay đổi giao diện: ảnh trước / sau ở desktop và mobile. -->

## Checklist trước khi merge

- [ ] `python -m unittest discover -s tests -v` chạy thành công.
- [ ] CI (`.github/workflows/ci.yml`) trên PR này đã xanh.
- [ ] Mọi trang render 200, các liên kết CSS/route đều tồn tại.
- [ ] Không thêm thư viện CSS/JS bên ngoài (Bootstrap, Tailwind, CDN font, icon...); icon dùng SVG inline hoặc CSS thuần.
- [ ] Không thay đổi bảng màu design tokens nếu chỉ sửa bố cục.
- [ ] Đã cập nhật `README.md` / stylesheet tương ứng khi thêm trang hoặc component mới.
- [ ] Đã tự review diff, không commit file rỗng, file IDE (`.idea/`) hay `__pycache__/`.
