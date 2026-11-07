-- Schema SQLite cho Freesion (phần cửa hàng + tài khoản; admin dùng chung bảng).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name           TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone               TEXT,
    password_hash       TEXT NOT NULL,
    birthday            TEXT,                       -- YYYY-MM-DD
    gender              TEXT CHECK (gender IN ('nam', 'nu', 'khac')),
    newsletter          INTEGER NOT NULL DEFAULT 0,
    role                TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    password_updated_at TEXT,
    session_version     INTEGER NOT NULL DEFAULT 0,  -- tăng lên để đăng xuất mọi thiết bị
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS password_resets (
    token      TEXT PRIMARY KEY,                    -- lưu SHA-256 của token
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS categories (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    slug     TEXT NOT NULL UNIQUE,
    name     TEXT NOT NULL,
    tone     TEXT NOT NULL DEFAULT 'beige',
    position INTEGER NOT NULL DEFAULT 0
);

-- Nhóm màu dùng cho bộ lọc (8 ô màu ở trang Shop).
CREATE TABLE IF NOT EXISTS color_families (
    slug     TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    hex      TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

-- Màu cụ thể của từng sản phẩm ("Trắng kem", "Nâu dừa"...), thuộc một nhóm màu.
CREATE TABLE IF NOT EXISTS colors (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    slug   TEXT NOT NULL UNIQUE,
    name   TEXT NOT NULL,
    hex    TEXT NOT NULL,
    family TEXT NOT NULL REFERENCES color_families(slug)
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    sku           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    price         INTEGER NOT NULL CHECK (price >= 0),          -- VND
    compare_price INTEGER CHECK (compare_price IS NULL OR compare_price > price),
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    department    TEXT NOT NULL CHECK (department IN ('nu', 'nam', 'phu-kien')),
    tone          TEXT NOT NULL DEFAULT 'beige',                -- màu nền placeholder ảnh
    material      TEXT,
    model_info    TEXT,
    care          TEXT,
    is_new        INTEGER NOT NULL DEFAULT 0,
    is_featured   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'draft', 'archived')),
    sold_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status   ON products(status);

CREATE TABLE IF NOT EXISTS product_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url        TEXT,                                -- NULL = dùng placeholder theo tone
    tone       TEXT NOT NULL DEFAULT 'beige',
    label      TEXT,
    position   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_images_product ON product_images(product_id, position);

CREATE TABLE IF NOT EXISTS variants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    color_id   INTEGER NOT NULL REFERENCES colors(id),
    size       TEXT NOT NULL,
    sku        TEXT NOT NULL UNIQUE,
    stock      INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    UNIQUE (product_id, color_id, size)
);
CREATE INDEX IF NOT EXISTS idx_variants_product ON variants(product_id);

CREATE TABLE IF NOT EXISTS reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    author_name   TEXT NOT NULL,
    city          TEXT,
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    fit           INTEGER CHECK (fit BETWEEN 1 AND 5),          -- 1 chật ... 5 rộng
    title         TEXT,
    body          TEXT NOT NULL,
    body_info     TEXT,                                         -- "Cao 1m65 · 55kg · Mua size M"
    verified      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);

CREATE TABLE IF NOT EXISTS testimonials (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    author     TEXT NOT NULL,
    city       TEXT,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    rating     INTEGER NOT NULL DEFAULT 5,
    quote      TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS wishlist (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS provinces (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    province_code TEXT NOT NULL REFERENCES provinces(code) ON DELETE CASCADE,
    name          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS addresses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label      TEXT,                                -- "Nhà riêng", "Công ty"
    full_name  TEXT NOT NULL,
    phone      TEXT NOT NULL,
    province   TEXT NOT NULL,
    ward       TEXT NOT NULL,
    street     TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id);

CREATE TABLE IF NOT EXISTS coupons (
    code        TEXT PRIMARY KEY COLLATE NOCASE,
    percent     INTEGER NOT NULL CHECK (percent BETWEEN 1 AND 100),
    min_order   INTEGER NOT NULL DEFAULT 0,
    max_discount INTEGER,                           -- NULL = không giới hạn
    expires_at  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1
);

-- Giỏ hàng: của người dùng (user_id) hoặc khách (guest_token trong session).
CREATE TABLE IF NOT EXISTS carts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    guest_token  TEXT UNIQUE,
    coupon_code  TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cart_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id    INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    variant_id INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    UNIQUE (cart_id, variant_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,           -- FR261101028
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    full_name       TEXT NOT NULL,
    phone           TEXT NOT NULL,
    email           TEXT NOT NULL,
    province        TEXT NOT NULL,
    ward            TEXT NOT NULL,
    street          TEXT NOT NULL,
    note            TEXT,
    shipping_method TEXT NOT NULL,
    shipping_fee    INTEGER NOT NULL DEFAULT 0,
    payment_method  TEXT NOT NULL,
    payment_status  TEXT NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid', 'paid', 'refunded')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'preparing', 'shipping', 'delivered', 'cancelled')),
    subtotal        INTEGER NOT NULL,
    discount        INTEGER NOT NULL DEFAULT 0,
    coupon_code     TEXT,
    total           INTEGER NOT NULL,
    vat_invoice     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    delivered_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    variant_id   INTEGER REFERENCES variants(id) ON DELETE SET NULL,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_slug TEXT,
    name         TEXT NOT NULL,
    color        TEXT NOT NULL,
    size         TEXT NOT NULL,
    tone         TEXT NOT NULL DEFAULT 'beige',
    price        INTEGER NOT NULL,                  -- đơn giá tại thời điểm đặt
    compare_price INTEGER,
    quantity     INTEGER NOT NULL CHECK (quantity > 0)
);

-- Mốc thời gian của đơn (hiển thị timeline ở trang chi tiết đơn).
CREATE TABLE IF NOT EXISTS order_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Nhắn tin khách <-> shop: mỗi khách có đúng một cuộc hội thoại với shop.
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    last_message_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender          TEXT NOT NULL CHECK (sender IN ('customer', 'shop')),
    sender_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,   -- nhân viên shop hoặc khách
    body            TEXT NOT NULL,
    order_code      TEXT,                                              -- tin nhắn gắn với một đơn hàng (tùy chọn)
    product_id      INTEGER REFERENCES products(id) ON DELETE SET NULL, -- hoặc một sản phẩm (tùy chọn)
    read_at         TEXT,                                              -- NULL = bên kia chưa đọc
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
