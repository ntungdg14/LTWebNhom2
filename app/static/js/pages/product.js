(function () {
    'use strict';
    const api = window.ShopAPI, auth = window.ShopAuth;
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