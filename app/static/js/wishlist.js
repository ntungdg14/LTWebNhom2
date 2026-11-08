/* Trang "Sản phẩm yêu thích": hiển thị danh sách thật từ GET /api/account/wishlist.
   Nút × gọi DELETE /api/account/wishlist/<product_id>. Trang này đã bắt buộc đăng nhập. */
(function () {
    'use strict';
    const { api, el, money, errorMessage, productHref, productMedia } = FS;

    const grid = document.getElementById('wishlist-grid');
    if (!grid) return;
    const count = document.getElementById('wishlist-count');
    const notice = document.getElementById('wishlist-notice');
    let items = [];

    function showNotice(text) { notice.textContent = text || ''; notice.hidden = !text; }

    function updateCount() {
        count.textContent = items.length ? 'Bạn đang lưu ' + items.length + ' sản phẩm' : 'Bạn chưa lưu sản phẩm nào';
    }

    async function remove(p, card) {
        const res = await api('DELETE', '/api/account/wishlist/' + p.id);
        if (!res.ok) { showNotice(errorMessage(res)); return; }
        showNotice('');
        items = items.filter((x) => x.id !== p.id);
        card.remove();
        updateCount();
        if (!items.length) renderEmpty();
    }

    function card(p) {
        const colors = (p.colors || []).map((c) => c.name).join(', ');
        const onSale = p.compare_price && p.compare_price > p.price;
        const article = el('article', { class: 'product-card' });
        article.append(
            el('div', { class: 'wishlist-media' },
                el('a', { href: productHref(p), tabindex: '-1', 'aria-hidden': 'true' }, productMedia(p)),
                el('button', {
                    type: 'button', class: 'remove-fav', 'aria-label': 'Xóa ' + p.name + ' khỏi danh sách yêu thích',
                    onclick: () => remove(p, article),
                }, '×')),
            el('h2', null, el('a', { href: productHref(p) }, p.name)),
            el('p', { class: 'meta' }, p.in_stock === false ? (colors ? colors + ' · ' : '') + 'Hết hàng' : colors),
            el('p', { class: 'price' }, money(p.price), onSale ? ' ' : null, onSale ? el('s', null, money(p.compare_price)) : null),
            el('a', { href: productHref(p), class: 'btn btn-block mt-3' }, 'Chọn size & thêm vào giỏ'));
        return article;
    }

    function renderEmpty() {
        grid.replaceChildren(el('p', { class: 'muted' }, 'Chưa có sản phẩm yêu thích. ',
            el('a', { href: '/shop', class: 'link-underline' }, 'Khám phá sản phẩm')));
    }

    async function load() {
        const res = await api('GET', '/api/account/wishlist');
        if (res.status === 401) {
            window.location.href = '/login?next=/account/wishlist';
            return;
        }
        if (!res.ok) { showNotice(errorMessage(res)); return; }
        showNotice('');
        grid.removeAttribute('aria-busy');
        items = res.data.items || [];
        updateCount();
        if (items.length) grid.replaceChildren(...items.map(card)); else renderEmpty();
    }

    load();
})();
