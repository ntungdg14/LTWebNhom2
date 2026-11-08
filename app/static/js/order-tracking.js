/* Trang chi tiết đơn hàng: nối giao diện với
     GET  /api/orders/<mã>             thông tin đơn
     GET  /api/orders/<mã>/tracking    dòng thời gian (suy ra từ cột orders.status)
     POST /api/orders/<mã>/simulate    demo: chuyển đơn sang bước kế tiếp
     POST /api/account/orders/<mã>/cancel  hủy đơn
   Nếu API lỗi (chưa đăng nhập, sai mã đơn) thì giữ nguyên dữ liệu mẫu trong HTML và hiện thông báo. */
(function () {
    'use strict';
    const { api, el, money, fmtDateTime, fmtShort, fmtDay, errorMessage } = FS;

    const root = document.querySelector('[data-order-code]');
    if (!root) return;
    const code = root.dataset.orderCode;
    const $ = (id) => document.getElementById(id);

    const BADGE = { pending: 'badge-warn', preparing: 'badge-warn', shipping: 'badge-warn', delivered: 'badge-ok', cancelled: 'badge-danger' };
    const PAYMENT = { cod: 'Thanh toán khi nhận hàng (COD)', vnpay: 'VNPAY / Thẻ ATM nội địa', momo: 'Ví điện tử MoMo', card: 'Thẻ quốc tế' };

    function notice(text) {
        const box = $('order-notice');
        box.textContent = text || '';
        box.hidden = !text;
    }

    function renderTracking(t) {
        const steps = $('tracking-steps');
        steps.replaceChildren(...t.steps.map((s, i) => {
            const cls = s.state === 'done' ? 'is-done' : s.state === 'current' ? 'is-current' : s.state === 'cancelled' ? 'is-cancelled' : '';
            let sub = s.at ? fmtShort(s.at) : '';
            if (!sub && s.state === 'upcoming') sub = i === t.steps.length - 1 && t.estimated_delivery ? 'Dự kiến ' + fmtDay(t.estimated_delivery.from) + ' – ' + fmtDay(t.estimated_delivery.to) : 'Chưa tới';
            return el('li', { class: cls, title: s.description }, el('span', { class: 'tracking-dot' }), el('strong', null, s.label), el('small', null, sub));
        }));

        const current = t.steps[t.current_step];
        $('tracking-desc').textContent = current ? current.description : '';
        if (t.is_cancelled) $('tracking-eta').textContent = 'Đơn hàng đã hủy';
        else if (t.is_delivered) $('tracking-eta').textContent = 'Đã giao hàng' + (t.delivered_at ? ' lúc ' + fmtDateTime(t.delivered_at) : '');
        else if (t.estimated_delivery) $('tracking-eta').textContent = 'Dự kiến nhận: ' + fmtDay(t.estimated_delivery.from) + ' – ' + fmtDay(t.estimated_delivery.to);
        else $('tracking-eta').textContent = t.status_label;

        $('tracking-carrier').textContent = t.tracking_number
            ? 'Đơn vị vận chuyển: ' + t.carrier + ' · Mã vận đơn: ' + t.tracking_number
            : t.is_cancelled ? '' : 'Đơn vị vận chuyển và mã vận đơn sẽ hiển thị khi đơn hàng được bàn giao.';

        const canAdvance = !t.is_delivered && !t.is_cancelled;
        $('simulate-btn').hidden = !canAdvance;
    }

    function renderOrder(o) {
        $('order-title').textContent = '#' + o.code;
        $('order-meta').textContent = 'Đặt lúc ' + fmtDateTime(o.created_at) + ' · ' + o.line_count + ' dòng sản phẩm · Số lượng: ' + o.item_count;
        const badge = $('order-status');
        badge.textContent = o.status_label;
        badge.className = 'badge ' + (BADGE[o.status] || 'badge-warn');

        $('order-items').replaceChildren(...o.items.map((i) => {
            let action = null;
            if (i.can_review) {
                action = el('div', { class: 'line-actions' }, el('a', { class: 'btn btn-outline', href: '/product?slug=' + encodeURIComponent(i.product_slug) + '&review=1#reviews' }, 'Đánh giá sản phẩm'));
            } else if (i.reviewed) {
                action = el('div', { class: 'line-actions' }, el('a', { class: 'reviewed-tag', href: '/product?slug=' + encodeURIComponent(i.product_slug) + '#reviews' }, '✓ Bạn đã đánh giá sản phẩm này'));
            }
            const name = i.product_slug ? el('a', { href: '/product?slug=' + encodeURIComponent(i.product_slug) }, el('strong', null, i.name)) : el('strong', null, i.name);
            return el('div', { class: 'order-line' },
                el('div', { class: 'media media-sm media-' + (i.tone || 'taupe') }, 'Ảnh sản phẩm'),
                el('div', { class: 'grow' }, name,
                    el('p', { class: 'meta' }, 'Size ' + i.size + ' | ' + i.color, el('br'), money(i.price) + ' × ' + i.quantity), action),
                el('span', null, money(i.line_total)));
        }));

        const addr = $('order-address');
        addr.replaceChildren(el('strong', null, o.contact.full_name + ' : ' + o.contact.phone), el('br'), o.address.full, el('br'), o.contact.email || '');
        $('order-note').textContent = o.note ? 'Ghi chú: ' + o.note : '';

        const pay = $('order-payment');
        pay.replaceChildren(PAYMENT[o.payment_method] || o.payment_method, el('br'),
            el('span', { style: o.payment_status === 'paid' ? 'color:var(--green-700);' : 'color:var(--orange-600);' },
                o.payment_status_label + (o.payment_status === 'unpaid' ? ' · Cần trả ' + money(o.total) : '')),
            el('br'), o.shipping_method_name + ' · ' + (o.shipping_fee ? money(o.shipping_fee) : 'Miễn phí'));

        const rows = [['Tạm tính (' + o.item_count + ' sản phẩm)', money(o.subtotal)]];
        if (o.discount) rows.push(['Giảm giá' + (o.coupon_code ? ' · ' + o.coupon_code : ''), '-' + money(o.discount)]);
        rows.push(['Phí vận chuyển', o.shipping_fee ? money(o.shipping_fee) : 'Miễn phí']);
        $('order-summary').replaceChildren(el('h2', null, 'Tóm tắt thanh toán'),
            ...rows.map((r) => el('div', { class: 'summary-row' }, el('span', null, r[0]), el('span', null, r[1]))),
            el('div', { class: 'summary-total' }, el('span', null, 'Tổng cộng'), el('span', null, money(o.total))),
            el('p', { class: 'muted', style: 'font-size:0.75rem;' }, 'Đã bao gồm thuế GTGT.'));

        $('cancel-btn').hidden = !o.can_cancel;
    }

    async function load() {
        const [orderRes, trackRes] = await Promise.all([api('GET', '/api/orders/' + encodeURIComponent(code)), api('GET', '/api/orders/' + encodeURIComponent(code) + '/tracking')]);
        if (!orderRes.ok || !trackRes.ok) {
            const needLogin = orderRes.status === 401 || orderRes.status === 404;
            notice(needLogin
                ? 'Không tìm thấy đơn này hoặc bạn chưa đăng nhập, nên đang hiển thị dữ liệu mẫu. Hãy đăng nhập bằng tài khoản đã đặt đơn.'
                : errorMessage(orderRes.ok ? trackRes : orderRes));
            return;
        }
        notice('');
        renderOrder(orderRes.data.order);
        renderTracking(trackRes.data.tracking);
    }

    $('simulate-btn').addEventListener('click', async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        const res = await api('POST', '/api/orders/' + encodeURIComponent(code) + '/simulate', {});
        button.disabled = false;
        if (!res.ok) {
            notice(errorMessage(res));
            if (res.status === 403) button.hidden = true; // máy chủ đã tắt chế độ mô phỏng
            return;
        }
        notice('');
        renderOrder(res.data.order);
        renderTracking(res.data.tracking);
    });

    $('cancel-btn').addEventListener('click', async (event) => {
        if (!window.confirm('Bạn chắc chắn muốn hủy đơn hàng này?')) return;
        const button = event.currentTarget;
        button.disabled = true;
        const res = await api('POST', '/api/account/orders/' + encodeURIComponent(code) + '/cancel', {});
        button.disabled = false;
        if (!res.ok) { notice(errorMessage(res)); return; }
        load();
    });

    load();
})();
