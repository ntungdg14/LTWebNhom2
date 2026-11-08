/* Trang "Đơn hàng của tôi": hiển thị đơn thật từ GET /api/account/orders?status=&page=
   (lọc theo tab trạng thái, phân trang). Chưa đăng nhập thì giữ dữ liệu mẫu trong HTML. */
(function () {
    'use strict';
    const { api, el, money, fmtDay, errorMessage } = FS;

    const list = document.getElementById('order-list');
    if (!list) return;
    const tabs = document.getElementById('order-tabs');
    const pager = document.getElementById('order-pagination');
    const notice = document.getElementById('order-list-notice');
    const BADGE = { pending: 'badge-warn', preparing: 'badge-warn', shipping: 'badge-warn', delivered: 'badge-ok', cancelled: 'badge-danger' };
    const state = { status: 'all', page: 1 };

    function showNotice(text) { notice.textContent = text || ''; notice.hidden = !text; }

    function card(o) {
        const detail = '/account/orders/' + encodeURIComponent(o.code);
        const lines = o.items.map((i) => el('div', { class: 'order-line' },
            el('div', { class: 'media media-sm media-' + (i.tone || 'taupe') }, 'Ảnh sản phẩm'),
            el('div', { class: 'grow' }, el('h2', null, i.name), el('p', { class: 'meta' }, 'Size ' + i.size + ' | ' + i.color + ' · ' + money(i.price) + ' × ' + i.quantity)),
            el('span', null, money(i.line_total))));
        const canReview = o.items.some((i) => i.can_review);
        return el('article', { class: 'order-card' },
            el('header', { class: 'row-between' },
                el('div', null, el('p', null, el('a', { href: detail }, el('strong', null, '#' + o.code))), el('p', { class: 'meta' }, 'Ngày đặt: ' + fmtDay(o.created_at))),
                el('span', { class: 'badge ' + (BADGE[o.status] || 'badge-warn') }, o.status_label)),
            ...lines,
            el('footer', { class: 'row-between mt-4' },
                el('p', { class: 'muted' }, o.line_count + ' dòng sản phẩm · Tổng số lượng: ' + o.item_count + '  |  ', el('strong', null, money(o.total))),
                el('div', { class: 'toolbar' },
                    el('a', { class: 'btn btn-ghost', href: detail }, 'Xem chi tiết'),
                    canReview ? el('a', { class: 'btn', href: detail }, 'Đánh giá') : null)));
    }

    function renderPager(data) {
        pager.replaceChildren();
        pager.hidden = data.pages <= 1;
        for (let n = 1; n <= data.pages; n++) {
            pager.append(el('a', { href: '#', class: 'page-num' + (n === data.page ? ' is-active' : ''), onclick: (e) => { e.preventDefault(); state.page = n; load(); } }, n));
        }
    }

    async function load() {
        const res = await api('GET', '/api/account/orders?status=' + state.status + '&page=' + state.page);
        if (res.status === 401) {
            showNotice('Bạn chưa đăng nhập nên đang xem dữ liệu mẫu. Đăng nhập để xem đơn hàng thật của bạn.');
            return;
        }
        if (!res.ok) { showNotice(errorMessage(res)); return; }
        showNotice('');
        const data = res.data;
        list.replaceChildren(...(data.items.length ? data.items.map(card) : [el('p', { class: 'muted' }, 'Chưa có đơn hàng nào.')]));
        renderPager(data);
    }

    tabs.addEventListener('click', (e) => {
        const link = e.target.closest('a[data-status]');
        if (!link) return;
        e.preventDefault();
        state.status = link.dataset.status;
        state.page = 1;
        tabs.querySelectorAll('a').forEach((a) => a.classList.toggle('is-active', a === link));
        load();
    });

    load();
})();
