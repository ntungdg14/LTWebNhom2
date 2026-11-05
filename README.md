# Freesion

Demo cửa hàng thời trang xây bằng **Python + Flask** (render phía server bằng Jinja2, dữ liệu mẫu nằm trực tiếp trong template).

## Chạy dự án

```bash
# Cách 1: uv (theo pyproject.toml / uv.lock)
uv sync
uv run python run.py

# Cách 2: pip + venv
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install flask
python run.py
```

Mặc định server chạy ở `http://localhost:5000`. Có thể đổi bằng biến môi trường
`FLASK_CONFIG` (`development` | `production` | `testing`), `FLASK_RUN_HOST`,
`FLASK_RUN_PORT`, `SECRET_KEY`.

Chạy kiểm thử:

```bash
python -m unittest discover -s tests -v
```

## Cây thư mục

```
.
├── app/
│   ├── __init__.py              # application factory: nạp config, đăng ký blueprint + filter `vnd`
│   ├── config.py                # Development / Production / Testing config
│   ├── commerce.py              # view-model: products/cart_items/order_items -> dict cho template
│   ├── blueprints/              # mỗi nhóm chức năng là một package Blueprint
│   │   ├── __init__.py          # danh sách blueprint đăng ký vào app
│   │   ├── store/               #    /  /shop  /product  /cart  /terms  /privacy  /help
│   │   ├── auth/                #    /login  /register  /forgot-password
│   │   ├── checkout/            #    /checkout/shipping  /checkout  /order-success
│   │   ├── account/             #    /account  /account/orders/<id>  /address  /wishlist
│   │   └── admin/               #    /admin + 17 route quản trị (xem bảng đường dẫn)
│   │       ├── __init__.py      # khai báo Blueprint
│   │       └── routes.py        # view + render_template
│   ├── templates/
│   │   ├── layouts/             # base.html + các layout kế thừa theo khu vực
│   │   │   ├── partials/        # _site_header, _site_footer, _admin_sidebar, _account_nav,
│   │   │   │                    # _checkout_steps (thanh tiến trình 4 bước)
│   │   │   ├── macros/          # _commerce.html: cart_card / order_item_card / order_summary_card
│   │   │   ├── base.html        # khung <html>, nạp CSS nền tảng, block styles/body
│   │   │   ├── base_store.html  # header + footer cửa hàng
│   │   │   ├── base_auth.html   # + CSS chung cho 3 trang xác thực
│   │   │   ├── base_account.html# + CSS chung cho 4 trang tài khoản
│   │   │   └── base_admin.html  # sidebar quản trị + CSS chung cho admin
│   │   ├── store/  auth/  checkout/  account/  admin/   # trang theo từng blueprint
│   └── static/
│       ├── css/                 # (xem sơ đồ bên dưới)
│       ├── js/nav-indicator.js  # đo vị trí tab; hiệu ứng trượt do CSS đảm nhận
│       └── images/              # dành cho ảnh sản phẩm về sau
├── db/schema.sql                # schema SQLite tham chiếu (tên cột = khóa view-model)
├── tests/
│   ├── test_routes.py           # 29 test: route, link, form, header, footer
│   └── test_commerce_components.py  # 16 test: card/container, dữ liệu, tổng tiền
├── .github/
│   ├── workflows/ci.yml         # build + test trên mỗi PR (GitHub Actions)
│   └── pull_request_template.md # mẫu mô tả PR
├── .gitignore
├── pyproject.toml / uv.lock
└── run.py                       # entry point chạy development server
```

## CSS:

```
app/static/css/
├── base.css                    # :root design tokens, reset, typography, utilities
├── components.css              # nút, input, thẻ sản phẩm, badge, phân trang, summary…
├── components/
│   └── commerce.css            # card giỏ hàng / card tóm tắt đơn hàng (flex + grid)
├── layouts/
│   ├── store.css               # header 2 hàng, ô tìm kiếm, mega menu + thanh trượt hover
│   ├── footer.css              # footer (tách riêng, không phụ thuộc store.css)
│   └── admin.css               # sidebar / vùng nội dung admin
└── pages/                      # mirror theo cây templates/
    ├── store/       home.css  shop.css  product_detail.css  cart.css
    ├── auth/        auth.css (dùng chung)  login.css  register.css  forgot_password.css
    ├── checkout/    checkout.css  order_success.css  steps.css (dùng chung 3 trang)
    ├── account/     account.css (dùng chung)  profile.css  order_history.css  address.css  wishlist.css
    └── admin/       admin.css (chung)  dashboard.css  products.css  orders.css  users.css
                     forms.css (4 form mới)
```

## Khối thông tin (component) & hợp đồng dữ liệu

Mỗi **đơn vị thông tin** được gom trong đúng một khung chứa thật (HTML cha → con),
không phải các phần tử rời rạc chỉnh margin/position cho có vẻ thành nhóm.

| Component (macro trong `layouts/macros/_commerce.html`) | Khung chứa | Nội dung bên trong |
|---|---|---|
| `cart_card(item)` | `<article class="cart-card">` | ảnh, tên, biến thể, giá, bộ đếm số lượng, **Xóa**, thành tiền |
| `order_item_card(item)` | `<article class="order-item-card">` | ảnh, tên, màu/size, đơn giá × số lượng, thành tiền |
| `order_summary_card(order, …)` | `<section class="order-summary-card">` | tiêu đề → **danh sách card sản phẩm** → dòng tạm tính/giảm giá/phí vận chuyển/tổng cộng → footer (mã giảm giá, CTA, ghi chú) |
| `product_media(image, …)` | `<img>` hoặc placeholder `<div>` | ảnh `product_images.url`, fallback theo `tone` |

Trang chi tiết sản phẩm dùng thêm `.info-card` cho từng nhóm (tiêu đề, màu, size,
mua hàng) và **một** `.product-description-card` chứa mô tả + `<dl>` thông số
(chất liệu, người mẫu, ghi chú). CSS cho card nằm ở
`css/components/commerce.css` (nạp từ `base.html`) và `css/pages/store/cart.css`;
khoảng cách do `gap` của container cha quyết định, không có inline positioning.

**Dữ liệu cho backend:** `app/commerce.py` chuẩn bị view-model, tên trường bám
`db/schema.sql`. Template chỉ lặp `{% for %}` và định dạng tiền bằng filter
`|vnd` (đăng ký trong `create_app`), không chứa tên sản phẩm/giá viết cứng.

| View-model | Bảng trong `db/schema.sql` |
|---|---|
| `get_product()` / `get_related()` | `products` + `product_images` + `colors` + `variants` |
| `get_cart()["items"]` | `cart_items` + `variants` + `products` + `colors` |
| `get_order()` / `get_order_history()` | `orders` + `order_items` + `coupons` |

Số tiền là `int` VND đúng kiểu cột SQL; `line_total`, `subtotal`, `discount`,
`total` và các dòng `rows` được tính trong `commerce.py`. Để nối CSDL thật, chỉ
cần thay thân các hàm `get_*` bằng truy vấn SQLite trả dict cùng khóa —
macro/CSS/route giữ nguyên.

## Header cửa hàng

`layouts/partials/_site_header.html` gồm **2 hàng** (bố cục tham khảo header CANIFA),
toàn bộ style nằm ở `css/layouts/store.css`. Footer được tách riêng sang
`css/layouts/footer.css` (nạp ngay sau `store.css` trong `base_store.html`) để
việc chỉnh header không bao giờ làm ảnh hưởng footer:

1. **Hàng trên**: logo `FREESION` bên trái → ô **tìm kiếm** (`<form method="get">`
   gửi `q` tới `/shop`) → 3 tiện ích có icon phía trên nhãn: Cửa hàng, Tài khoản,
   Giỏ hàng. Icon là **SVG inline** (`currentColor`), không dùng thư viện icon hay CDN.
2. **Hàng dưới**: thanh danh mục ngang (Nữ, Nam, Phụ kiện, Hàng mới, Sale); mục
   đang chọn được đánh dấu bằng gạch chân.

### Mega menu khi di chuột

Mỗi mục có một panel thả xuống hiện ra khi **di chuột** (`:hover`) hoặc khi
**focus bằng bàn phím** (`:focus-within`) — hoàn toàn bằng CSS, không JavaScript,
không thư viện ngoài. Panel gồm 4 cột: liên kết nhanh, **Danh mục sản phẩm**
(chia 2 cột con, có badge `HOT`), **Phụ kiện**, **Bộ sưu tập**. Dữ liệu panel
được khai báo bằng `{% set %}` + một Jinja macro trong `_site_header.html`.

Không đưa vào menu các mục CANIFA S / LICENSE / SCHOOL / ĐỒNG PHỤC và **không dùng
2 ảnh chân dung** của ảnh tham khảo; chỉ giữ 5 mục của Freesion. Panel thu gọn
còn 2 cột dưới 1024px, 1 cột dưới 768px.

Chỉ thay đổi **bố cục**: mọi màu vẫn lấy từ design tokens trong `base.css`
(`--bg`, `--white`, `--stone-*`, `--orange-600`), không đưa thêm màu mới.
Responsive: dưới 768px ô tìm kiếm xuống hàng riêng, dưới 480px các tiện ích chỉ
giữ icon (nhãn vẫn có trong DOM để hỗ trợ trình đọc màn hình).

## Đường dẫn

Bảng đầy đủ các route sau khi rà soát (không còn link `#`, link trỏ nhầm trang hay route trùng lặp).

| Đường dẫn | Trang / chức năng tương ứng | Ghi chú |
| --- | --- | --- |
| `/` | Trang chủ | Giữ nguyên; bổ sung danh mục, bộ sưu tập, đánh giá, 3 ưu điểm |
| `/shop` | Danh sách sản phẩm | Giữ nguyên; thêm breadcrumb, bộ lọc màu/size/giá, link `?sku=` riêng |
| `/product` | Chi tiết sản phẩm | Giữ nguyên; thêm lưới ảnh 6 ô, điểm đánh giá, review, link `?sku=` |
| `/cart` | Giỏ hàng | Giữ nguyên; sửa nút thanh toán sang `/checkout/shipping`, thêm mã giảm giá + gợi ý |
| `/checkout/shipping` | Thông tin giao hàng (bước 2) | MỚI — tách riêng khỏi trang thanh toán |
| `/checkout` | Thanh toán (bước 3) | Giữ nguyên; thêm thanh tiến trình, 4 phương thức thanh toán |
| `/order-success` | Xác nhận đơn hàng (bước 4) | Giữ nguyên; đổi liên kết sang trang chi tiết đơn |
| `/login` | Đăng nhập | Giữ nguyên; cập nhật nhãn, icon mật khẩu, link điều khoản |
| `/register` | Đăng ký | Giữ nguyên; sửa 2 link điều khoản (trước cùng trỏ `/`) |
| `/forgot-password` | Quên mật khẩu | Giữ nguyên; thêm liên kết trợ giúp |
| `/terms` | Điều khoản sử dụng | MỚI — đích riêng cho link điều khoản |
| `/privacy` | Chính sách bảo mật | MỚI — đích riêng cho link bảo mật |
| `/help` | Hỗ trợ kỹ thuật / liên hệ | MỚI — dùng cho footer và form xác thực |
| `/account` | Tài khoản của bạn | Giữ nguyên; bổ sung đổi mật khẩu, địa chỉ mặc định |
| `/account/orders` | Lịch sử đơn hàng | Giữ nguyên; thêm tab trạng thái, tìm kiếm |
| `/account/orders/<order_id>` | Chi tiết đơn hàng (khách) | MỚI — thay link "Xem chi tiết" trỏ nhầm `/order-success` |
| `/account/address` | Sổ địa chỉ | Giữ nguyên; mỗi thao tác có `?action=` riêng |
| `/account/wishlist` | Sản phẩm yêu thích | Giữ nguyên; mỗi sản phẩm có `?remove=` / `?add=` riêng |
| `/admin` | Tổng quan quản trị | Giữ nguyên; thêm thẻ thống kê, biểu đồ cột CSS, "Cần xử lý" |
| `/admin/products` | Quản lý sản phẩm | Giữ nguyên; thêm stat/tab, nút thêm sản phẩm, link sửa |
| `/admin/products/new` | Form thêm sản phẩm | MỚI (Nhiệm vụ 3) — POST điều hướng về danh sách |
| `/admin/products/<sku>/edit` | Chỉnh sửa sản phẩm | MỚI — dùng lại form thêm sản phẩm ở chế độ sửa |
| `/admin/categories` | Quản lý danh mục | MỚI — đích cho mục sidebar "Danh mục" |
| `/admin/categories/new` | Form thêm danh mục | MỚI (Nhiệm vụ 3) |
| `/admin/orders` | Quản lý đơn hàng | Giữ nguyên; thêm stat/tab, sửa link chi tiết |
| `/admin/orders/<order_id>` | Chi tiết đơn hàng (admin) | MỚI — thay link trỏ nhầm `/order-success` |
| `/admin/users` | Quản lý khách hàng | Giữ nguyên; thêm stat/tab, nút thêm khách hàng |
| `/admin/users/new` | Form thêm khách hàng | MỚI (Nhiệm vụ 3) |
| `/admin/users/<customer_id>` | Hồ sơ khách hàng (admin) | MỚI — thay link trỏ nhầm `/account` |
| `/admin/permissions` | Form phân quyền tài khoản | MỚI (Nhiệm vụ 3) — tìm kiếm + lọc vai trò + quyền hiện tại |
| `/admin/inventory` | Quản lý kho hàng | MỚI — mục sidebar theo ảnh |
| `/admin/promotions` | Quản lý khuyến mãi | MỚI — mục sidebar theo ảnh |
| `/admin/reports` | Báo cáo | MỚI — mục sidebar theo ảnh |

Các liên kết lọc/phân trang dùng query string riêng biệt (`?page=2`, `?status=pending`, `?sku=FR-BOM-002`…), không còn nhiều link cùng trỏ một URL. `tests/test_routes.py` duyệt **toàn bộ href/action nội bộ** trên 33 trang trong bộ kiểm thử và kiểm tra từng URL trả 200.

## Form quản trị mới

- `/admin/products/new`, `/admin/categories/new`, `/admin/users/new`: cùng dùng `.field`, `.input`, `.btn`, `.form-stack`, `.admin-card` của `components.css` nên giữ nguyên màu, font, bo góc, khoảng cách và kiểu input/nút.
- `/admin/permissions`: một form chứa thanh tìm kiếm (`name="q"`, bỏ dấu tiếng Việt), bộ lọc vai trò (`name="role"`: Tất cả / Quản trị viên / Khách hàng) ngay bên dưới, và danh sách tài khoản kèm **quyền hiện tại** + ô đổi quyền. Nút "Lưu thay đổi" gửi POST, hai nút lọc gửi GET.
- Dữ liệu là mock tĩnh (không có CSDL): POST chỉ xác nhận và điều hướng về trang danh sách kèm banner.

## Hiệu ứng navbar

Giữ nguyên cấu trúc, vị trí và nội dung header/navbar. Các nút navbar dùng cùng hiệu ứng chuyển màu mượt (`transition: color 0.2s ease`) với Cửa hàng / Tài khoản / Giỏ hàng; thêm `.nav-indicator` — thanh ngang `var(--stone-950)` trượt theo tab đang hover nhờ `transition: transform, width` trong `store.css`. `static/js/nav-indicator.js` (JavaScript thuần, không thư viện) chỉ đo vị trí/độ rộng bằng `getBoundingClientRect()`; không có JS thì navbar vẫn hoạt động bình thường.
## CI

`.github/workflows/ci.yml` chạy trên mỗi PR vào `master` (và khi push `master`):
cài Python 3.14 + `uv`, `uv sync --frozen`, biên dịch/import ứng dụng rồi chạy
`python -m unittest discover -s tests -v`. Khi mở PR, nội dung được điền sẵn từ
`.github/pull_request_template.md` (mô tả, loại thay đổi, ảnh chụp màn hình,
checklist).

## Đóng góp

Xem [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
