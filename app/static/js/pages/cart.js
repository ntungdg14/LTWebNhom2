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
})();
