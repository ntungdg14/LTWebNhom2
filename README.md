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
├── tests/test_routes.py         # kiểm thử route + stylesheet bằng unittest
├── .gitignore
├── pyproject.toml / uv.lock
└── run.py                       # entry point chạy development server
```

## CSS: đã dọn gì?

* **Xóa `app/static/css/main.css`** (1 file 1.106 dòng) → tách thành các file nhỏ theo từng tầng và từng trang.
* **Loại bỏ CSS bên ngoài không dùng**: bỏ hoàn toàn `<link>` Google Fonts / `preconnect`
  trong layout. `--font` trong `base.css` giờ dùng system font stack, nên trang web
  không còn phụ thuộc CDN, tải offline được và không có request ra ngoài.
  Không còn Bootstrap / Tailwind / thư viện CSS bên thứ ba nào; đồng thời xóa các
  rule chết không được template nào dùng (`.container`, `.text-center`, `.mt-2`).
* Mỗi trang HTML có **đúng 1 stylesheet riêng**, nạp qua `{% block styles %}{{ super() }}`.
  Thứ tự nạp (cascade) luôn là: nền tảng → thành phần → layout → khu vực → trang.

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

| Trang HTML | Stylesheet riêng | CSS chung của khu vực |
| --- | --- | --- |
| `store/*.html` | `pages/store/<tên trang>.css` | `layouts/store.css` |
| `auth/*.html` | `pages/auth/<tên trang>.css` | `pages/auth/auth.css` (qua `base_auth.html`) |
| `checkout/*.html` | `pages/checkout/<tên trang>.css` | `layouts/store.css` |
| `account/*.html` | `pages/account/<tên trang>.css` | `pages/account/account.css` (qua `base_account.html`) |
| `admin/*.html` | `pages/admin/<tên trang>.css` | `layouts/admin.css` + `pages/admin/admin.css` |

> `base.html` nạp `base.css` và `components.css` cho mọi trang. Các file trong
> `pages/` chỉ chứa rule riêng của trang đó; rule dùng từ 2 trang trở lên nằm ở
> `components.css` hoặc file CSS chung của khu vực để tránh lặp code.

## Endpoint (sau khi tách blueprint)

`url_for()` trong template dùng tên có namespace, ví dụ `url_for('store.home')`,
`url_for('auth.login')`, `url_for('admin.products')`. Đường dẫn URL công khai vẫn
giữ nguyên như cũ.
