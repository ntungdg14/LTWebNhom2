/* Tiện ích dùng chung cho JavaScript của Freesion: gọi API JSON, tạo phần tử DOM, định dạng. */
(function () {
    'use strict';

    // Gọi API. Luôn trả { ok, status, data } (không ném lỗi khi server trả 4xx/5xx).
    async function api(method, url, body) {
        const options = { method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
        if (body !== undefined) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
        try {
            const res = await fetch(url, options);
            let data = null;
            try { data = await res.json(); } catch (e) { /* phản hồi không phải JSON */ }
            return { ok: res.ok, status: res.status, data: data || {} };
        } catch (e) {
            return { ok: false, status: 0, data: { error: { message: 'Không kết nối được máy chủ.' } } };
        }
    }

    // Lấy thông báo lỗi dễ đọc từ phản hồi API (gồm cả lỗi theo từng trường).
    function errorMessage(res) {
        const err = (res.data && res.data.error) || {};
        const fields = err.fields ? Object.values(err.fields) : [];
        return fields.length ? fields.join(' ') : (err.message || 'Có lỗi xảy ra, vui lòng thử lại.');
    }

    // Tạo phần tử: el('div', { class: 'x', onclick: fn }, 'chữ', otherNode ...). Chữ luôn là text (an toàn XSS).
    function el(tag, attrs) {
        const node = document.createElement(tag);
        Object.entries(attrs || {}).forEach(([key, value]) => {
            if (value === null || value === undefined || value === false) return;
            if (key === 'class') node.className = value;
            else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
            else node.setAttribute(key, value === true ? '' : value);
        });
        for (let i = 2; i < arguments.length; i++) {
            const child = arguments[i];
            if (child === null || child === undefined || child === false) continue;
            node.append(child.nodeType ? child : document.createTextNode(String(child)));
        }
        return node;
    }

    const money = (n) => Number(n || 0).toLocaleString('vi-VN') + '₫';

    // "2026-11-08 15:47:17" -> Date (giờ địa phương)
    function parseDate(text) {
        return text ? new Date(String(text).replace(' ', 'T')) : null;
    }
    function fmtDateTime(text) {
        const d = parseDate(text);
        if (!d || isNaN(d)) return '';
        const p = (n) => String(n).padStart(2, '0');
        return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} · ${p(d.getHours())}:${p(d.getMinutes())}`;
    }
    function fmtShort(text) {
        const d = parseDate(text);
        if (!d || isNaN(d)) return '';
        const p = (n) => String(n).padStart(2, '0');
        return `${p(d.getDate())}/${p(d.getMonth() + 1)} · ${p(d.getHours())}:${p(d.getMinutes())}`;
    }
    function fmtDay(iso) {
        if (!iso) return '';
        const [y, m, d] = String(iso).slice(0, 10).split('-');
        return `${d}/${m}/${y}`;
    }
    function timeAgo(text) {
        const d = parseDate(text);
        if (!d || isNaN(d)) return '';
        const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
        if (s < 60) return 'Vừa xong';
        if (s < 3600) return Math.floor(s / 60) + ' phút trước';
        if (s < 86400) return Math.floor(s / 3600) + ' giờ trước';
        if (s < 86400 * 30) return Math.floor(s / 86400) + ' ngày trước';
        return fmtDay(String(text).slice(0, 10));
    }
    const stars = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);


    // ---- Thẻ sản phẩm dùng chung (trang chủ, shop, yêu thích) ----
    const productHref = (p) => '/product?slug=' + encodeURIComponent(p.slug);

    // Ô ảnh khi chưa có ảnh thật: nền theo màu sản phẩm, chỉ hiện tên sản phẩm.
    // size: 'card' (mặc định) | 'thumb' | 'sm' | 'xs'
    function placeholderMedia(p, size) {
        const tone = p.tone || (p.image && p.image.tone) || 'taupe';
        const hex = p.colors && p.colors[0] && p.colors[0].hex;
        const box = el('div', { class: 'media media-' + (size || 'card') + ' media-empty media-' + tone, role: 'img', 'aria-label': p.name + ' (ảnh đang cập nhật)' });
        if (hex && /^#[0-9a-f]{6}$/i.test(hex)) box.style.setProperty('--ph-color', hex);
        box.append(el('span', { class: 'ph-name' }, p.name || 'Ảnh sản phẩm'));
        return box;
    }

    // Vẽ ảnh sản phẩm: có url thì dùng <img>, chưa có ảnh thì dùng ô trống đẹp (placeholderMedia).
    function productMedia(p) {
        const img = p.image || {};
        const tone = p.tone || img.tone || 'taupe';
        return img.url
            ? el('div', { class: 'media media-card media-' + tone }, el('img', { src: img.url, alt: p.name, loading: 'lazy' }))
            : placeholderMedia(p);
    }

    // Nút trái tim thêm/bỏ yêu thích. Chưa đăng nhập (401) thì chuyển sang trang đăng nhập.
    function wishButton(p) {
        const btn = el('button', { type: 'button', class: 'fav-btn' });
        const paint = () => {
            btn.classList.toggle('is-on', !!p.in_wishlist);
            btn.setAttribute('aria-pressed', p.in_wishlist ? 'true' : 'false');
            btn.setAttribute('aria-label', (p.in_wishlist ? 'Bỏ yêu thích ' : 'Thêm vào yêu thích ') + p.name);
            btn.textContent = p.in_wishlist ? '♥' : '♡';
        };
        let busy = false;
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (busy) return;
            busy = true;
            const res = p.in_wishlist
                ? await api('DELETE', '/api/account/wishlist/' + p.id)
                : await api('POST', '/api/account/wishlist', { product_id: p.id });
            busy = false;
            if (res.status === 401) { window.location.href = '/login'; return; }
            if (res.ok) { p.in_wishlist = !p.in_wishlist; paint(); }
        });
        paint();
        return btn;
    }

    // Thẻ sản phẩm từ một phần tử của API (/api/products, /api/home, /api/account/wishlist).
    function productCard(p, heading) {
        const colors = (p.colors || []).map((c) => c.name).join(', ');
        const onSale = p.compare_price && p.compare_price > p.price;
        return el('article', { class: 'product-card' },
            el('div', { class: 'card-media' },
                el('a', { href: productHref(p), tabindex: '-1', 'aria-hidden': 'true' }, productMedia(p)),
                wishButton(p)),
            el(heading || 'h3', null, el('a', { href: productHref(p) }, p.name)),
            el('p', { class: 'meta' }, p.in_stock === false ? (colors ? colors + ' · ' : '') + 'Hết hàng' : colors),
            el('p', { class: 'price' }, money(p.price), onSale ? ' ' : null, onSale ? el('s', null, money(p.compare_price)) : null));
    }

    window.FS = { api, errorMessage, el, money, fmtDateTime, fmtShort, fmtDay, timeAgo, stars, productHref, productMedia, placeholderMedia, wishButton, productCard };
})();
