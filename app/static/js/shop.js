(function () {
    'use strict';
    const api = window.ShopAPI, auth = window.ShopAuth;
    const money = n => new Intl.NumberFormat('vi-VN').format(n || 0) + '₫';
    const status = document.querySelector('#cart-status');
    const items = document.querySelector('#cart-items');
    function node(tag, text, className) {
        const el = document.createElement(tag); el.textContent = text;
        if (className) el.className = className;
        return el;
    }
    function renderCart(cart) {
        items.replaceChildren();
        if (!cart.items.length) items.append(node('p', 'Giỏ hàng đang trống.'));
        cart.items.forEach(item => {
            const article = node('article', '', 'cart-item');
            const info = node('div', '', 'grow');
            const title = node('h2', item.product.name);
            info.append(title, node('p', `Size ${item.size} | ${item.color.name}`, 'meta'), node('p', money(item.price), 'price'));
            const remove = node('button', 'Xóa', 'link-underline');
            remove.type = 'button'; remove.dataset.itemId = item.id; remove.dataset.quantity = 0;
            info.append(remove);
            const qty = node('div', '', 'qty');
            for (const [text, quantity] of [['−', item.quantity - 1], ['+', item.quantity + 1]]) {
                const button = node('button', text); button.type = 'button';
                button.dataset.itemId = item.id; button.dataset.quantity = quantity;
                qty.append(button);
            }
            qty.insertBefore(node('span', String(item.quantity)), qty.children[1]);
            article.append(info, qty, node('span', money(item.line_total), 'cart-line-total'));
            items.append(article);
        });
        for (const [id, value] of Object.entries({
            'cart-subtotal': cart.subtotal, 'cart-shipping': cart.shipping_fee,
            'cart-discount': cart.discount, 'cart-total': cart.total
        })) document.getElementById(id).textContent = money(value);
        status.textContent = cart.has_issues ? 'Có sản phẩm không còn đủ hàng.' : '';
    }
    if (items) {
        api.cart().then(data => renderCart(data.cart)).catch(err => { status.textContent = err.message; });
        items.addEventListener('click', async e => {
            const button = e.target.closest('[data-item-id]'); if (!button || button.disabled) return;
            button.disabled = true;
            try { renderCart((await api.changeItem(button.dataset.itemId, Number(button.dataset.quantity))).cart); }
            catch (err) { status.textContent = err.message; button.disabled = false; }
        });
        document.getElementById('cart-coupon').addEventListener('submit', async e => {
            e.preventDefault(); const button = e.target.querySelector('button'); button.disabled = true;
            try { renderCart((await api.coupon(new FormData(e.target).get('coupon'))).cart); }
            catch (err) { status.textContent = err.message; } finally { button.disabled = false; }
        });
    }
    document.querySelectorAll('[data-add-cart], [data-buy-now]').forEach(button => button.addEventListener('click', async () => {
        await auth.ready;
        if (!auth.requireUser()) return;
        if (button.disabled) return;
        button.disabled = true;
        try {
            // Current detail page is a static showcase; resolve its actual seeded variant from the API.
            const sku = new URLSearchParams(location.search).get('sku') || 'FR-BOM-002';
            const products = await api.request('/products?q=' + encodeURIComponent(sku));
            const card = products.items.find(item => item.sku === sku);
            if (!card) throw new Error('Không tìm thấy sản phẩm đang chọn.');
            const product = (await api.product(card.slug)).product;
            const color = new URLSearchParams(location.search).get('color') || 'nau-dua';
            const size = new URLSearchParams(location.search).get('size') || 'M';
            const variant = (product.colors.find(c => c.slug === color) || product.colors[0])?.sizes.find(s => s.size === size && s.stock > 0);
            if (!variant) throw new Error('Kích cỡ này đã hết hàng. Vui lòng chọn kích cỡ khác.');
            await api.addItem(variant.variant_id);
            location.assign(button.matches('[data-buy-now]') ? '/checkout/shipping' : '/cart');
        } catch (err) { auth.message(err.message); button.disabled = false; }
    }));
})();
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
