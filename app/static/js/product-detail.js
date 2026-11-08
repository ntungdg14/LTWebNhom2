/* Trang chi tiết sản phẩm: thay nội dung mẫu bằng dữ liệu thật.
     GET  /api/products/<slug>          ảnh, màu -> size -> variant_id/tồn kho, mô tả, chất liệu...
     GET  /api/products/<slug>/related  "Có thể bạn cũng thích"
     POST /api/cart/items               "Thêm vào giỏ hàng" / "Mua ngay" ({ variant_id, quantity })
   Slug lấy từ ?slug= trên URL, mặc định theo data-product-slug của trang. Màu/size đang chọn được ghi lên URL
   (?color=<slug màu>&size=<size>). Phần đánh giá do reviews.js đảm nhiệm. Nếu API lỗi, giữ dữ liệu mẫu. */
(function () {
    'use strict';
    const { api, el, money, errorMessage, productCard } = FS;

    const root = document.querySelector('[data-product-slug]');
    const title = document.getElementById('pd-title');
    if (!root || !title) return;

    const $ = (id) => document.getElementById(id);
    const params = new URLSearchParams(location.search);
    const slug = params.get('slug') || root.dataset.productSlug;
    const DEPARTMENTS = { nu: 'Nữ', nam: 'Nam', 'phu-kien': 'Phụ kiện' };
    const state = { product: null, colorSlug: null, size: null, busy: false };

    // ---------------------------------------------------------------- thông báo
    function showMsg(text, kind, withCartLink) {
        const box = $('pd-msg');
        box.replaceChildren();
        box.hidden = !text;
        box.classList.toggle('is-ok', kind === 'ok');
        if (!text) return;
        box.append(text);
        if (withCartLink) box.append(' ', el('a', { href: '/cart', class: 'link-underline' }, 'Xem giỏ hàng'));
    }

    // ----------------------------------------------------------- dữ liệu đang chọn
    const currentColor = () => state.product.colors.find((c) => c.slug === state.colorSlug) || null;
    function currentVariant() {
        const color = currentColor();
        return color ? color.sizes.find((s) => s.size === state.size) || null : null;
    }

    // ----------------------------------------------------------------- vẽ từng phần
    function renderHeader(p) {
        document.title = p.name + ' - FREESION';
        title.textContent = p.name;
        $('pd-eyebrow').textContent = p.category.name + ' · ' + (DEPARTMENTS[p.department] || '');
        const onSale = p.compare_price && p.compare_price > p.price;
        $('pd-price').replaceChildren(money(p.price), onSale ? ' ' : '', onSale ? el('s', null, money(p.compare_price)) : '');
        $('pd-breadcrumb').replaceChildren(
            el('a', { href: '/' }, 'Trang chủ'), ' / ',
            el('a', { href: '/shop?department=' + encodeURIComponent(p.department) }, DEPARTMENTS[p.department] || 'Cửa hàng'), ' / ',
            p.name);
        const r = p.rating;
        if (r) {
            const avg = r.average ? String(r.average).replace('.', ',') : '';
            $('product-rating').replaceChildren(
                r.count ? FS.stars(Math.round(r.average)) + ' ' : '',
                r.count ? el('span', null, avg) : '',
                r.count ? ' · ' + r.count + ' đánh giá' : 'Chưa có đánh giá');
        }
    }

    function renderGallery(p) {
        // Ô ảnh chưa có ảnh thật mà ghi "người mẫu" thì bỏ đi (trang không hiển thị người mẫu).
        const shown = p.images.filter((img) => img.url || !/người mẫu/i.test(img.label || ''));
        const tiles = shown.map((img) => (img.url
            ? el('div', { class: 'media media-card media-' + (img.tone || p.tone || 'taupe') }, el('img', { src: img.url, alt: img.label || p.name, loading: 'lazy' }))
            : el('div', { class: 'media media-card media-' + (img.tone || p.tone || 'taupe') }, img.label || p.name)));
        $('pd-gallery').replaceChildren(...(tiles.length ? tiles : [FS.placeholderMedia({ name: p.name, tone: p.tone, colors: p.colors }, 'card')]));
    }

    function renderColors(p) {
        const color = currentColor();
        $('pd-color-name').textContent = 'Màu sắc: ' + (color ? color.name : '');
        $('pd-swatches').replaceChildren(...p.colors.map((c) => el('button', {
            type: 'button',
            class: 'swatch' + (c.slug === state.colorSlug ? ' is-active' : '') + (c.in_stock ? '' : ' is-soldout'),
            style: /^#[0-9a-f]{6}$/i.test(c.hex || '') ? 'background:' + c.hex : null,
            title: c.name + (c.in_stock ? '' : ' (hết hàng)'),
            'aria-label': c.name + (c.in_stock ? '' : ' (hết hàng)'),
            'aria-pressed': c.slug === state.colorSlug ? 'true' : 'false',
            onclick: () => pickColor(c.slug),
        })));
    }

    function renderSizes(p) {
        const color = currentColor();
        $('pd-sizes').replaceChildren(...p.sizes.map((size) => {
            const variant = color && color.sizes.find((s) => s.size === size);
            const available = !!variant && variant.stock > 0;
            return el('button', {
                type: 'button',
                class: 'size-btn' + (size === state.size ? ' is-active' : '') + (available ? '' : ' is-soldout'),
                disabled: !available,
                'aria-pressed': size === state.size ? 'true' : 'false',
                title: available ? null : 'Hết hàng',
                onclick: () => pickSize(size),
            }, size);
        }));
    }

    function renderStock() {
        const v = currentVariant();
        const box = $('pd-stock');
        let text = '';
        if (!v || v.stock <= 0) text = 'Phiên bản này đã hết hàng.';
        else if (v.stock <= 5) text = 'Chỉ còn ' + v.stock + ' sản phẩm.';
        box.textContent = text;
        box.hidden = !text;
        const soldOut = !v || v.stock <= 0;
        [$('pd-add'), $('pd-buy')].forEach((b) => { b.disabled = soldOut || state.busy; });
    }

    function renderNotes(p) {
        const rows = [['Chất liệu', p.material], ['Ghi chú', p.care]].filter((r) => r[1]);
        $('pd-notes').replaceChildren(
            el('h2', null, 'Mô tả sản phẩm'),
            p.description ? el('p', null, p.description) : null,
            ...rows.map(([k, v]) => el('div', { class: 'summary-row' }, el('span', null, k), el('span', null, v))));
    }

    function syncUrl() {
        const q = new URLSearchParams(location.search);
        q.set('slug', slug);
        if (state.colorSlug) q.set('color', state.colorSlug);
        if (state.size) q.set('size', state.size);
        history.replaceState(null, '', location.pathname + '?' + q.toString());
    }

    function renderChoices() {
        renderColors(state.product);
        renderSizes(state.product);
        renderStock();
        syncUrl();
    }

    // ------------------------------------------------------------------- chọn màu / size
    function firstAvailableSize(color, preferred) {
        const ok = (s) => color.sizes.find((x) => x.size === s && x.stock > 0);
        if (preferred && ok(preferred)) return preferred;
        const first = color.sizes.find((x) => x.stock > 0);
        return first ? first.size : (preferred && color.sizes.some((x) => x.size === preferred) ? preferred : (color.sizes[0] || {}).size || null);
    }

    function pickColor(colorSlug) {
        state.colorSlug = colorSlug;
        state.size = firstAvailableSize(currentColor(), state.size);
        showMsg('');
        renderChoices();
    }

    function pickSize(size) {
        state.size = size;
        showMsg('');
        renderChoices();
    }

    // ------------------------------------------------------------ thêm vào giỏ / mua ngay
    async function addToCart(goCheckout) {
        const v = currentVariant();
        if (!v) { showMsg('Vui lòng chọn màu và kích cỡ.', 'error'); return; }
        if (state.busy) return;
        state.busy = true;
        renderStock();
        const res = await api('POST', '/api/cart/items', { variant_id: v.variant_id, quantity: 1 });
        state.busy = false;
        renderStock();
        if (res.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search); return; }
        if (!res.ok) { showMsg(errorMessage(res), 'error'); return; }
        if (goCheckout) { location.href = '/checkout/shipping'; return; }
        showMsg('Đã thêm vào giỏ hàng.', 'ok', true);
    }

    $('pd-add').addEventListener('click', () => addToCart(false));
    $('pd-buy').addEventListener('click', () => addToCart(true));

    // ------------------------------------------------------------------ sản phẩm gợi ý
    async function loadRelated() {
        const res = await api('GET', '/api/products/' + encodeURIComponent(slug) + '/related?limit=4');
        const box = $('pd-related-box');
        if (!res.ok) return;
        const items = res.data.items || [];
        if (!items.length) { box.hidden = true; return; }
        $('pd-related').replaceChildren(...items.map((p) => productCard(p)));
    }

    // ------------------------------------------------------------------------- khởi động
    (async function load() {
        const res = await api('GET', '/api/products/' + encodeURIComponent(slug));
        if (!res.ok) {
            showMsg(res.status === 404 ? 'Không tìm thấy sản phẩm này. Đang hiển thị dữ liệu mẫu.' : errorMessage(res) + ' Đang hiển thị dữ liệu mẫu.', 'error');
            // Không có dữ liệu thật thì không cho thêm vào giỏ.
            $('pd-add').disabled = true;
            $('pd-buy').disabled = true;
            return;
        }
        const p = res.data.product;
        state.product = p;
        const wantedColor = params.get('color');
        const start = p.colors.find((c) => c.slug === wantedColor) || p.colors.find((c) => c.in_stock) || p.colors[0] || null;
        state.colorSlug = start ? start.slug : null;
        state.size = start ? firstAvailableSize(start, (params.get('size') || '').toUpperCase()) : null;

        renderHeader(p);
        renderGallery(p);
        renderNotes(p);
        renderChoices();
        loadRelated();
    })();
})();
