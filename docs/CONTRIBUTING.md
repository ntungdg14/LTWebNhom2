# Quy ước chung

Mỗi thành viên thực hiện theo quy trình sau:

1. Đồng bộ branch làm việc với branch đích.
2. Tạo branch riêng cho chức năng hoặc lỗi cần xử lý.
3. Phát triển và kiểm thử thay đổi trên branch đó.
4. Commit các thay đổi theo quy ước của dự án.
5. Push branch lên GitHub.
6. Tạo Pull Request vào branch đích.
7. Chờ review, xử lý góp ý và bảo đảm các kiểm tra CI thành công.
8. Chỉ merge sau khi đáp ứng các yêu cầu của nhóm.

## Quy tắc đặt tên branch

Sử dụng các tiền tố sau:

| Tiền tố | Mục đích | Ví dụ |
|---|---|---|
| `feat/` | Thêm chức năng | `feat/product-filter` |
| `fix/` | Sửa lỗi | `fix/cart-quantity` |
| `refactor/` | Tái cấu trúc code | `refactor/store-routes` |
| `style/` | Thay đổi giao diện | `style/product-detail` |
| `test/` | Thêm hoặc sửa test | `test/store-routes` |
| `docs/` | Cập nhật tài liệu | `docs/contributing-guide` |
| `ci/` | Cấu hình CI/CD | `ci/github-actions` |
| `chore/` | Công việc bảo trì | `chore/update-dependencies` |

Tên branch nên ngắn gọn, viết thường, không dấu và dùng dấu gạch ngang để phân tách từ.

## Quy tắc commit

`<type>: <mô tả ngắn gọn>`

Các loại commit:

| Type | Ý nghĩa |s
|---|---|
| `feat` | Thêm chức năng |
| `fix` | Sửa lỗi |
| `refactor` | Tái cấu trúc code |
| `style` | Thay đổi giao diện hoặc định dạng |
| `test` | Thêm hoặc cập nhật kiểm thử |
| `docs` | Cập nhật tài liệu |
| `ci` | Thay đổi CI/CD |
| `chore` | Công việc bảo trì |

Ví dụ:

```text
feat: add product filtering
fix: correct cart quantity update
style: improve product detail layout
test: add store route tests
docs: add contributing guide
ci: configure pull request checks
```