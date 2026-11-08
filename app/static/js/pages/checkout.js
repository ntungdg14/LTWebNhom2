(function () {
    'use strict';
    const api = window.ShopAPI, auth = window.ShopAuth;
    const shipping = document.querySelector('#shipping-form');
    const payment = document.querySelector('#payment-form');
    const status = document.querySelector('#checkout-status');
    if (shipping) {
        auth.ready.then(user => { if (user) { shipping.elements.full_name.value = user.full_name; shipping.elements.email.value = user.email; shipping.elements.phone.value = user.phone || ''; } });
        shipping.addEventListener('submit', e => {
            e.preventDefault();
            const values = Object.fromEntries(new FormData(shipping));
            sessionStorage.setItem('shop:shipping', JSON.stringify(values));
            location.assign('/checkout');
        });
    }
    if (payment) {
        const raw = sessionStorage.getItem('shop:shipping');
        if (!raw) { location.replace('/checkout/shipping'); return; }
        api.cart().then(({cart}) => {
            if (!cart.items.length) { status.textContent = 'Giỏ hàng đang trống.'; payment.querySelector('button').disabled = true; }
            else document.getElementById('checkout-summary').textContent = `${cart.item_count} sản phẩm · Tạm tính ${new Intl.NumberFormat('vi-VN').format(cart.subtotal)}₫ (phí giao hàng được tính lại khi đặt hàng)`;
        }).catch(err => { status.textContent = err.message; });
        payment.addEventListener('submit', async e => {
            e.preventDefault(); const button = payment.querySelector('button');
            if (button.disabled) return; button.disabled = true; status.textContent = 'Đang đặt hàng…';
            try {
                const values = JSON.parse(sessionStorage.getItem('shop:shipping'));
                const { order } = await api.order({ ...values, payment_method: new FormData(payment).get('payment_method'), accept_terms: true });
                sessionStorage.removeItem('shop:shipping');
                location.assign('/order-success?code=' + encodeURIComponent(order.code));
            } catch (err) { status.textContent = err.fields && Object.values(err.fields)[0] || err.message; button.disabled = false; }
        });
    }
    const result = document.getElementById('order-result');
    if (result) {
        const code = new URLSearchParams(location.search).get('code');
        if (code) api.request('/orders/' + encodeURIComponent(code)).then(({order}) => { result.textContent = `Mã đơn ${order.code} · ${order.status_label}`; }).catch(err => { result.textContent = err.message; });
        else result.textContent = 'Không có mã đơn hàng.';
    }
})();
