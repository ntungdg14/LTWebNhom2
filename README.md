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
│   ├── config.py                # Development / Production / Testing config
│   ├── blueprints/              # mỗi nhóm chức năng là một package Blueprint
│   │   ├── __init__.py          # danh sách blueprint đăng ký vào app
│   │   ├── store/               #    /  /shop  /product  /cart
│   │   ├── auth/                #    /login  /register  /forgot-password
│   │   ├── checkout/            #    /checkout  /order-success
│   │   ├── account/             #    /account  /account/orders  /address  /wishlist
│   │   └── admin/               #    /admin  /admin/products  /orders  /users
│   │       ├── __init__.py      # khai báo Blueprint
│   │       └── routes.py        # view + render_template
│   ├── templates/
│   │   ├── layouts/             # base.html + các layout kế thừa theo khu vực
│   │   │   ├── partials/        # _site_header, _site_footer, _admin_sidebar, _account_nav
│   │   │   ├── base.html        # khung <html>, nạp CSS nền tảng, block styles/body
│   │   │   ├── base_store.html  # header + footer cửa hàng
│   │   │   ├── base_auth.html   # + CSS chung cho 3 trang xác thực
│   │   │   ├── base_account.html# + CSS chung cho 4 trang tài khoản
│   │   │   └── base_admin.html  # sidebar quản trị + CSS chung cho admin
│   │   ├── store/  auth/  checkout/  account/  admin/   # trang theo từng blueprint
│   └── static/
│       ├── css/                 # (xem sơ đồ bên dưới)
│       ├── js/                  # dành cho JavaScript về sau
│       └── images/              # dành cho ảnh sản phẩm về sau
├── tests/test_routes.py         # kiểm thử route, stylesheet và bố cục header
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
│   ├── store.css               # header / nav / footer
│   └── admin.css               # sidebar / vùng nội dung admin
└── pages/                      # mirror theo cây templates/
    ├── store/       home.css  shop.css  product_detail.css  cart.css
    ├── auth/        auth.css (dùng chung)  login.css  register.css  forgot_password.css
    ├── checkout/    checkout.css  order_success.css
    ├── account/     account.css (dùng chung)  profile.css  order_history.css  address.css  wishlist.css
    └── admin/       admin.css (dùng chung)  dashboard.css  products.css  orders.css  users.css
```

## Header cửa hàng

`layouts/partials/_site_header.html` gồm **2 hàng** (bố cục tham khảo header CANIFA),
toàn bộ style nằm ở `css/layouts/store.css`:

1. **Hàng trên**: logo `FREESION` bên trái → ô **tìm kiếm** (`<form method="get">`
   gửi `q` tới `/shop`) → 3 tiện ích có icon phía trên nhãn: Cửa hàng, Tài khoản,
   Giỏ hàng. Icon là **SVG inline** (`currentColor`), không dùng thư viện icon hay CDN.
2. **Hàng dưới**: thanh danh mục ngang (Nữ, Nam, Phụ kiện, Hàng mới, Sale), có thể
   cuộn ngang trên màn hình hẹp; mục đang chọn được đánh dấu bằng gạch chân.

Chỉ thay đổi **bố cục**: mọi màu vẫn lấy từ design tokens trong `base.css`
(`--bg`, `--white`, `--stone-*`, `--orange-600`), không đưa thêm màu mới.
Responsive: dưới 768px ô tìm kiếm xuống hàng riêng, dưới 480px các tiện ích chỉ
giữ icon (nhãn vẫn có trong DOM để hỗ trợ trình đọc màn hình).

## CI

`.github/workflows/ci.yml` chạy trên mỗi PR vào `master` (và khi push `master`):
cài Python 3.14 + `uv`, `uv sync --frozen`, biên dịch/import ứng dụng rồi chạy
`python -m unittest discover -s tests -v`. Khi mở PR, nội dung được điền sẵn từ
`.github/pull_request_template.md` (mô tả, loại thay đổi, ảnh chụp màn hình,
checklist).

## Đóng góp

Xem [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
