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
│   ├── __init__.py              # application factory: nạp config, đăng ký blueprint
│   ├── config.py                # Development / Production / Testing config (+ phí ship, thanh toán)
│   ├── db.py                    # kết nối SQLite, transaction, lệnh flask init-db / seed-db
│   ├── schema.sql               # schema CSDL (SQLite)
│   ├── seed.py                  # dữ liệu mẫu (danh mục, màu, sản phẩm, mã giảm giá, tỉnh/phường)
│   ├── blueprints/              # mỗi nhóm chức năng là một package Blueprint
│   │   ├── __init__.py          # danh sách blueprint đăng ký vào app
│   │   ├── store/               #    /  /shop  /product  /cart  /terms  /privacy  /help
│   │   │   ├── routes.py        #    trang HTML
│   │   │   ├── api.py           #    API sản phẩm: /api/home, /categories, /colors, /products...
│   │   │   └── cart_api.py      #    API giỏ hàng + mã giảm giá: /api/cart...
│   │   ├── auth/                #    /login  /register  /forgot-password
│   │   │   ├── routes.py
│   │   │   └── api.py           #    /api/auth/... (đăng ký, đăng nhập, quên/đặt lại mật khẩu)
│   │   ├── checkout/            #    /checkout/shipping  /checkout  /order-success
│   │   │   ├── routes.py
│   │   │   ├── api.py           #    /api/checkout/options, /api/orders...
│   │   │   └── locations_api.py #    /api/provinces, /api/provinces/<code>/wards
│   │   ├── account/             #    /account  /account/orders/<id>  /address  /wishlist
│   │   │   ├── routes.py
│   │   │   └── api.py           #    /api/account/... (hồ sơ, địa chỉ, yêu thích, đơn của tôi)
│   │   ├── chat/                #    chỉ có API (chưa có trang HTML)
│   │   │   ├── __init__.py      #    chat_api_bp
│   │   │   └── api.py           #    /api/chat/... (khách) và /api/shop/chat/... (shop = admin)
│   │   └── admin/               #    /admin + 17 route quản trị (trang HTML, không có API)
│   │       ├── __init__.py      # khai báo Blueprint
│   │       └── routes.py        # view + render_template
│   ├── common/                  # dùng chung cho các file api.py
│   │   ├── errors.py            # lỗi JSON cho mọi URL /api/...
│   │   ├── helpers.py           # ApiError, kiểm tra dữ liệu, xác thực JWT
│   │   ├── serializers.py       # định dạng JSON trả về
│   │   ├── services.py          # giỏ hàng, giá, mã giảm giá, phí ship
│   │   └── tracking.py          # theo dõi đơn (mô phỏng): timeline từ orders.status, đẩy đơn sang bước kế
│   ├── templates/
│   │   ├── layouts/             # base.html + các layout kế thừa theo khu vực
│   │   │   ├── partials/        # _site_header, _site_footer, _admin_sidebar, _account_nav,
│   │   │   │                    # _checkout_steps (thanh tiến trình 4 bước)
│   │   │   ├── base.html        # khung <html>, nạp CSS nền tảng, block styles/body
│   │   │   ├── base_store.html  # header + footer cửa hàng
│   │   │   ├── base_auth.html   # + CSS chung cho 3 trang xác thực
│   │   │   ├── base_account.html# + CSS chung cho 4 trang tài khoản
│   │   │   └── base_admin.html  # sidebar quản trị + CSS chung cho admin
│   │   ├── store/  auth/  checkout/  account/  admin/   # trang theo từng blueprint
│   └── static/
│       ├── css/                 # (xem sơ đồ bên dưới)
│       ├── js/
│       │   ├── core/            # api.js (fetch + CSRF), auth.js (phiên và form xác thực)
│       │   ├── components/      # nav-indicator.js (hiệu ứng navbar)
│       │   └── pages/           # cart.js, product.js, checkout.js (chỉ nạp ở trang tương ứng)
│       └── images/              # dành cho ảnh sản phẩm về sau
├── tests/test_routes.py         # 29 test: route, link, form, header, footer
├── tests/test_api.py            # test API (SQLite tạm + dữ liệu mẫu)
├── tests/test_frontend_auth.py  # test form, header và route guard
├── tests/test_jwt_auth.py       # test JWT/CSRF/thu hồi token
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

## API

Mỗi blueprint có file `api.py` riêng (xem cây thư mục), URL bắt đầu bằng `/api`, dùng SQLite theo `app/schema.sql`. Mỗi package khai báo thêm một blueprint `*_api_bp` (`url_prefix="/api"`) trong `__init__.py`.
**Không có API quản trị** (trang `/admin` vẫn là mock); ngoại lệ duy nhất là API trả lời tin nhắn của shop (`/api/shop/chat/...`, cần `role = admin`). Các trang HTML hiện tại vẫn là mock; giao diện gọi API bằng `fetch` khi cần.

```bash
flask --app run init-db     # tạo bảng (cũng tự chạy khi khởi động app)
flask --app run seed-db     # nạp dữ liệu mẫu (chỉ khi chưa có sản phẩm)
```

File CSDL mặc định `instance/freesion.db`; đổi bằng biến môi trường `DATABASE`.

Quy ước: body gửi lên là JSON (`Content-Type: application/json`); đăng nhập bằng JWT HS256 trong cookie `access_token` HttpOnly (không gửi Bearer token).
Lỗi luôn có dạng `{"error": {"code", "message", "fields"?}}` (400 sai tham số, 401 chưa đăng nhập,
404 không thấy, 409 xung đột như hết hàng, 422 dữ liệu không hợp lệ).

| Nhóm | Phương thức & đường dẫn | Mô tả |
| --- | --- | --- |
| Auth | `POST /api/auth/register` · `login` · `logout` · `GET /api/auth/me` | Đăng ký (tự đăng nhập), đăng nhập (`remember`), đăng xuất, người dùng hiện tại |
| Auth | `POST /api/auth/forgot-password` · `reset-password` | Token lưu dạng SHA-256, hết hạn 60 phút, dùng một lần |
| Cửa hàng | `GET /api/home` · `/api/categories` · `/api/colors` | Dữ liệu trang chủ, danh mục, nhóm màu cho bộ lọc |
| Cửa hàng | `GET /api/products` | Lọc `department, category, color, size, price_min, price_max, q, is_new, sale, featured, exclude`; `sort`; `page, per_page`; kèm `facets` đếm theo danh mục |
| Cửa hàng | `GET /api/products/<slug>` · `/related` | Chi tiết (ảnh, màu → size → `variant_id`/tồn kho, điểm đánh giá) và sản phẩm gợi ý |
| Cửa hàng | `GET/POST /api/products/<slug>/reviews` | Danh sách đánh giá + thống kê sao/độ vừa vặn; gửi đánh giá (cần đăng nhập, `verified` nếu đã nhận hàng, mỗi người một đánh giá/sản phẩm). Mỗi đánh giá có `is_mine` |
| Cửa hàng | `PATCH/DELETE /api/reviews/<id>` | Sửa (chỉ gửi trường cần đổi, `null` để xóa trường tùy chọn) / xóa đánh giá của chính mình; trả lại `summary` mới. Xóa xong được đánh giá lại |
| Giỏ hàng | `GET/DELETE /api/cart` | Giỏ của khách (cookie) hoặc người dùng; `?shipping_method=standard\|express` để tính phí |
| Giỏ hàng | `POST /api/cart/items` · `PATCH/DELETE /api/cart/items/<id>` | Thêm (cộng dồn), đổi số lượng (0 = xóa), xóa dòng; kiểm tồn kho |
| Giỏ hàng | `POST/DELETE /api/cart/coupon` | Áp / bỏ mã giảm giá (kiểm tra hạn, đơn tối thiểu, mức giảm tối đa) |
| Đặt hàng | `GET /api/checkout/options` | Phương thức giao hàng (phí + ngày dự kiến) và thanh toán |
| Đặt hàng | `POST /api/orders` · `GET /api/orders/<code>` | Tạo đơn từ giỏ (trừ kho trong một transaction, server tự tính tiền); xem đơn (chủ đơn, khách vừa đặt trong phiên, hoặc admin). Mỗi dòng hàng có `reviewed` / `can_review` (đơn đã giao và chưa đánh giá) |
| Đặt hàng | `GET /api/orders/<code>/tracking` | Theo dõi đơn **(mô phỏng)**: đọc cột `orders.status` rồi trả `steps` (`done`/`current`/`upcoming`, kèm mốc giờ từ `order_events`), `current_step`, `tracking_number` (từ bước đang giao), `estimated_delivery`. Đơn hủy: các bước đã qua + bước `cancelled` |
| Đặt hàng | `POST /api/orders/<code>/simulate` | Demo: đẩy đơn sang bước kế (`pending → preparing → shipping → delivered`); body tùy chọn `{"to": "shipping"}` để nhảy tới bước đó. Khi `delivered` ghi `delivered_at`, đơn COD chuyển `paid`. Chỉ khi `ORDER_SIMULATION` bật (Development/Testing) hoặc là admin |
| Tài khoản | `GET/PATCH /api/account/profile` · `POST /password` · `POST /logout-all` | Hồ sơ, đổi mật khẩu, đăng xuất mọi thiết bị |
| Tài khoản | `GET/POST /api/account/addresses` · `PATCH/DELETE /<id>` · `POST /<id>/default` | Sổ địa chỉ (địa chỉ đầu tiên tự là mặc định) |
| Tài khoản | `GET/POST /api/account/wishlist` · `DELETE /api/account/wishlist/<product_id>` | Yêu thích |
| Tài khoản | `GET /api/account/orders` · `POST /<code>/cancel` · `POST /<code>/reorder` | Lịch sử (`status=all\|processing\|delivered\|cancelled`, `q`), hủy đơn, mua lại |
| Tài khoản | `GET /api/account/reviews` | `items`: đánh giá của tôi (kèm sản phẩm); `pending`: sản phẩm đã nhận hàng nhưng chưa đánh giá (kèm mã đơn) |
| Nhắn tin (khách) | `GET /api/chat/conversation` · `GET/POST /api/chat/messages` · `GET /api/chat/unread` | Mỗi khách một hội thoại với shop, tạo ở tin đầu tiên. Gửi `{body, order_code?, product_slug?}` (gắn đơn/sản phẩm đang hỏi). Lấy tin: `limit`, `before_id` (tin cũ), `after_id` (polling tin mới), `mark_read=0` để không đánh dấu đã đọc |
| Nhắn tin (shop, admin) | `GET /api/shop/chat/conversations` · `GET/POST /api/shop/chat/conversations/<id>/messages` · `GET /api/shop/chat/unread` | Hộp thư của shop (`q` tên/email khách, `unread=1`, phân trang), đọc + trả lời từng khách. Khách thường gọi sẽ nhận 403 |
| Địa chỉ | `GET /api/provinces` · `/api/provinces/<code>/wards` | Tỉnh/thành và phường/xã |

Theo dõi đơn: chưa có đơn vị vận chuyển thật nên trạng thái hoàn toàn dựa vào cột `orders.status` (`pending`, `preparing`, `shipping`, `delivered`, `cancelled`); giao diện chỉ cần gọi `/tracking` và hiển thị theo `steps`. Chưa có websocket: chat dùng polling (`after_id`). Đặt `ORDER_SIMULATION = True` trong config để khách tự bấm "đẩy đơn" khi demo; production mặc định tắt. Bảng `conversations`/`messages` nằm trong `schema.sql` (`CREATE TABLE IF NOT EXISTS`), DB cũ tự có bảng mới khi khởi động app. Admin chưa có API đăng ký: đặt `UPDATE users SET role = 'admin' WHERE email = '...'` để có tài khoản shop.

Ghi chú nghiệp vụ: miễn phí ship chuẩn từ 499.000₫ (nếu không: 30.000₫), giao nhanh 35.000₫ — chỉnh trong
`config.py`. Thanh toán online (VNPAY/MoMo/thẻ) chưa tích hợp cổng nên đơn ở trạng thái `unpaid`
(`requires_online_payment: true`). Chưa có dịch vụ email: ở Development/Testing, `forgot-password` trả kèm
`reset_token` để thử.

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

Giữ nguyên cấu trúc, vị trí và nội dung header/navbar. Các nút navbar dùng cùng hiệu ứng chuyển màu mượt (`transition: color 0.2s ease`) với Cửa hàng / Tài khoản / Giỏ hàng; thêm `.nav-indicator` — thanh ngang `var(--stone-950)` trượt theo tab đang hover nhờ `transition: transform, width` trong `store.css`. `static/js/components/nav-indicator.js` (JavaScript thuần, không thư viện) chỉ đo vị trí/độ rộng bằng `getBoundingClientRect()`; không có JS thì navbar vẫn hoạt động bình thường.
## CI

`.github/workflows/ci.yml` chạy trên mỗi PR vào `master` (và khi push `master`):
cài Python 3.14 + `uv`, `uv sync --frozen`, biên dịch/import ứng dụng rồi chạy
`python -m unittest discover -s tests -v`. Khi mở PR, nội dung được điền sẵn từ
`.github/pull_request_template.md` (mô tả, loại thay đổi, ảnh chụp màn hình,
checklist).

## Đóng góp

Xem [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

### Tích hợp giao diện khách hàng (JWT)

Giao diện Jinja/JavaScript gọi API cùng origin; `API_BASE_URL` mặc định rỗng (không cần thiết lập khi chạy Flask trực tiếp). Nếu triển khai khác origin, phải cấu hình proxy cùng origin để JWT trong cookie HttpOnly được gửi đúng; không dùng localStorage. Đăng ký hiện tạo phiên ngay trên backend, giao diện **không gọi thêm đăng nhập** và quay về URL `next` (chỉ nhận đường dẫn tương đối nội bộ). Mật khẩu: tối thiểu 8 ký tự có chữ hoa, chữ thường và số.

Trang giỏ hàng, thanh toán và tài khoản được bảo vệ tại route Flask; các nút mua hàng kiểm tra phiên trước khi thao tác. Giỏ hàng và quy trình đặt hàng giao diện dùng API thực, không còn hiển thị mặt hàng mẫu trên các trang này. Một số trang khác (shop, chi tiết sản phẩm, hồ sơ/lịch sử đơn) vẫn có nội dung demo: việc chuyển toàn bộ các trang này sang dữ liệu API cần thực hiện ở giai đoạn tiếp theo. API backend giỏ hàng/đặt hàng vốn hỗ trợ khách vãng lai và vẫn như cũ; giới hạn đăng nhập hiện áp dụng cho **giao diện**, không phải bảo mật trực tiếp các endpoint đó. Thanh toán online chưa có cổng thanh toán; nên dùng COD khi kiểm thử.

Kiểm thử thủ công: mở `/register` nhập email mới và mật khẩu mạnh, thử xác nhận sai và email trùng; mở `/login` thử mật khẩu sai; mở `/cart?coupon=ABC` khi chưa đăng nhập để xác minh chuyển `/login?next=...`, đăng nhập rồi kiểm tra quay về giỏ; F5 để xác minh cookie JWT; tại `/product` bấm Thêm vào giỏ hoặc Mua ngay khi chưa đăng nhập và sau khi đăng nhập; trong giỏ thử tăng/giảm số lượng, mã giảm giá, qua giao hàng → thanh toán COD → nhận mã đơn. Đăng xuất bằng header rồi thử `/account/orders`. Để thử phiên hết hạn, ở tab khác gọi `POST /api/account/logout-all` với header `X-CSRF-Token` (hoặc xóa cookie `access_token` trong DevTools), sau đó thực hiện request được bảo vệ trên tab cũ.


#### JWT và CSRF

- Backend tạo JWT HS256 (claim `sub`, `sv`, `iat`, `exp`, `jti`, `csrf`, `iss`) tại đăng ký/đăng nhập. Cookie `access_token` luôn HttpOnly; cookie `csrf_token` để JavaScript đọc và gửi `X-CSRF-Token` trên POST/PATCH/DELETE. Backend đối chiếu header với claim đã ký trong JWT, kiểm tra `Origin` và từ chối 403 khi sai. Không trả JWT trong JSON, không lưu token trong localStorage.
- JWT có hạn 12 giờ; chọn “Ghi nhớ đăng nhập” thì 30 ngày. Logout thu hồi riêng JWT qua bảng `revoked_tokens`; logout-all/đổi mật khẩu tăng `session_version` để vô hiệu JWT cũ trên mọi thiết bị (đổi mật khẩu cấp JWT mới cho thiết bị hiện tại). Cookie Flask `session` vẫn dùng cho giỏ khách/mã đơn vừa đặt nhưng **không dùng để xác thực**; cookie phiên xác thực cũ không còn hiệu lực.
- Chạy local HTTP: mặc định `SESSION_COOKIE_SAMESITE=Lax`, `SESSION_COOKIE_SECURE=0`. Với Live Preview trong iframe HTTPS: khởi động bằng `SESSION_COOKIE_SAMESITE=None SESSION_COOKIE_SECURE=1 python run.py`. Trình duyệt tắt hoàn toàn third-party cookies cần mở preview trong tab riêng. Production cần đặt `SECRET_KEY` mạnh, dùng HTTPS (production luôn bật Secure).
- Các endpoint dành cho khách (giỏ khách, đặt hàng khách theo API gốc) vẫn giữ hợp đồng cũ; khi có JWT, request ghi dữ liệu phải có CSRF header. Các trang HTML bảo vệ và tất cả API cần tài khoản đều xác thực bằng JWT.


### Cấu trúc JavaScript

Script dùng chung chỉ nạp một lần từ `templates/layouts/base_store.html`, theo thứ tự
`core/api.js` → `core/auth.js` → `components/nav-indicator.js`. Script thuộc trang
được nạp qua block `scripts` ở template tương ứng: `pages/cart.js` tại giỏ hàng,
`pages/product.js` tại chi tiết sản phẩm và `pages/checkout.js` tại các bước đặt hàng.
HTML/Jinja và CSS vẫn được nhóm theo Blueprint (`store`, `auth`, `account`, `checkout`,
`admin`), không dồn phẳng như ví dụ minh họa vì các route và stylesheet đã tham chiếu
các đường dẫn phân nhóm này. `__pycache__`, `.venv`, `instance` là dữ liệu sinh ra
khi chạy và được `.gitignore` bỏ qua.
