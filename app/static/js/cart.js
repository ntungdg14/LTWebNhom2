/* Trang giỏ hàng: vẽ giỏ thật từ GET /api/cart (khách dùng cookie, người đăng nhập dùng tài khoản).
   - nút − / + : PATCH /api/cart/items/<id>     (số lượng 0 = xóa)
   - nút Xóa   : DELETE /api/cart/items/<id>
   - mã giảm giá: POST /api/cart/coupon, DELETE /api/cart/coupon
   Mọi API đều trả về cả giỏ mới nên mỗi thao tác chỉ cần vẽ lại một lần. Không gọi được API thì giữ dữ liệu mẫu. */
(function () {
    'use strict';
    const { api, el, money, errorMessage } = FS;

    const list = document.getElementById('cart-items');
    if (!list) return;
    const $ = (id) => document.getElementById(id);
    const head = $('cart-head');
    const notice = $('cart-notice');
    const couponForm = $('cart-coupon-form');
    const couponInput = $('cart-coupon-code');
    const couponMsg = $('cart-coupon-msg');
    const couponRemove = $('cart-coupon-remove');
    const checkout = $('cart-checkout');
    let busy = false;

    function showNotice(text) { notice.textContent = text || ''; notice.hidden = !text; }

    function showCouponMsg(text, ok) {
        couponMsg.textContent = text || '';
        couponMsg.hidden = !text;
        couponMsg.classList.toggle('is-ok', !!ok);
    }

    // Gửi thao tác rồi vẽ lại giỏ; trả true nếu thành công.
    async function act(method, url, body) {
        if (busy) return false;
        busy = true;
        list.classList.add('is-busy');
        try {
            const res = await api(method, url, body);
            if (res.ok) { showNotice(''); render(res.data.cart); return true; }
            showNotice(errorMessage(res));
            return false;
        } finally {
            busy = false;
            list.classList.remove('is-busy');
        }
    }

    function line(item) {
        const href = '/product?slug=' + encodeURIComponent(item.product.slug);
        const step = (label, text, qty) => el('a', {
            href: '#', 'aria-label': label,
            onclick: (e) => { e.preventDefault(); act('PATCH', '/api/cart/items/' + item.id, { quantity: qty }); },
        }, text);
        return el('article', { class: 'cart-item' },
            item.product.image.url
                ? el('div', { class: 'media media-thumb media-' + (item.product.image.tone || 'taupe') },
                    el('img', { src: item.product.image.url, alt: item.product.name, loading: 'lazy' }))
                : FS.placeholderMedia({ name: item.product.name, colors: [item.color], image: item.product.image }, 'thumb'),
            el('div', { class: 'grow' },
                el('h2', null, el('a', { href }, item.product.name)),
                el('p', { class: 'meta' }, 'Size ' + item.size + ' | ' + item.color.name),
                el('p', { class: 'price' }, money(item.price) + ' ',
                    item.compare_price && item.compare_price > item.price ? el('s', null, money(item.compare_price)) : null),
                item.issue ? el('p', { class: 'cart-issue' }, item.issue) : null,
                el('a', {
                    href: '#', class: 'link-underline',
                    onclick: (e) => { e.preventDefault(); act('DELETE', '/api/cart/items/' + item.id); },
                }, 'Xóa')),
            el('div', { class: 'qty' },
                step('Giảm số lượng', '−', item.quantity - 1),
                el('span', null, item.quantity),
                step('Tăng số lượng', '+', item.quantity + 1)),
            el('span', { class: 'cart-line-total' }, money(item.line_total)));
    }

    function render(cart) {
        const empty = cart.items.length === 0;
        head.hidden = empty;
        list.replaceChildren(...(empty
            ? [el('div', { class: 'cart-empty' }, el('p', null, 'Giỏ hàng của bạn đang trống.'),
                el('a', { href: '/shop', class: 'btn' }, 'Khám phá sản phẩm'))]
            : cart.items.map(line)));

        $('cart-subtotal-label').textContent = 'Tạm tính (' + cart.item_count + ' sản phẩm)';
        $('cart-subtotal').textContent = money(cart.subtotal);
        $('cart-shipping').textContent = empty || cart.shipping_fee === 0 ? (empty ? '—' : 'Miễn phí') : money(cart.shipping_fee);
        $('cart-total').textContent = money(cart.total);

        const row = $('cart-discount-row');
        row.hidden = !cart.coupon;
        if (cart.coupon) {
            $('cart-discount-label').textContent = 'Giảm giá (' + cart.coupon.code + ' · ' + cart.coupon.percent + '%)';
            $('cart-discount').textContent = '-' + money(cart.discount);
        }
        couponInput.value = cart.coupon ? cart.coupon.code : '';
        couponInput.readOnly = !!cart.coupon;
        couponRemove.hidden = !cart.coupon;
        couponForm.querySelector('button[type="submit"]').hidden = !!cart.coupon;
        // Mã đã áp nhưng nay không còn hợp lệ (vd. đơn dưới mức tối thiểu): báo cho khách.
        showCouponMsg(cart.coupon_error || '', false);

        $('cart-shipping-note').textContent = empty ? '' : (cart.free_shipping_remaining > 0
            ? 'Mua thêm ' + money(cart.free_shipping_remaining) + ' để được miễn phí vận chuyển. Bạn có 30 ngày để đổi trả.'
            : 'Đơn hàng đã đủ điều kiện miễn phí vận chuyển. Bạn có 30 ngày để đổi trả.');

        // Giỏ trống hoặc có dòng hết hàng thì không cho sang bước thanh toán.
        const blocked = empty || cart.has_issues;
        checkout.setAttribute('aria-disabled', blocked ? 'true' : 'false');
        checkout.tabIndex = blocked ? -1 : 0;
    }

    checkout.addEventListener('click', (e) => {
        if (checkout.getAttribute('aria-disabled') === 'true') {
            e.preventDefault();
            showNotice('Giỏ hàng trống hoặc có sản phẩm không còn đủ hàng, vui lòng kiểm tra lại.');
        }
    });

    couponForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const code = couponInput.value.trim();
        if (!code) { showCouponMsg('Vui lòng nhập mã giảm giá.', false); return; }
        if (busy) return;
        busy = true;
        const res = await api('POST', '/api/cart/coupon', { code });
        busy = false;
        if (res.ok) { showNotice(''); render(res.data.cart); showCouponMsg('Đã áp dụng mã ' + res.data.cart.coupon.code + '.', true); return; }
        showCouponMsg(errorMessage(res), false);
    });

    couponRemove.addEventListener('click', async () => {
        if (await act('DELETE', '/api/cart/coupon')) showCouponMsg('Đã bỏ mã giảm giá.', true);
    });

    (async function load() {
        const res = await api('GET', '/api/cart');
        if (!res.ok) {
            showNotice(res.status === 0 ? errorMessage(res) + ' Đang hiển thị dữ liệu mẫu.' : errorMessage(res));
            return;
        }
        render(res.data.cart);
    })();
})();
