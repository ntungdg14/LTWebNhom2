/* Same-origin by default; optional API_BASE_URL injected by the server for deployments. */
window.ShopAPI = (function () {
    'use strict';
    const base = (window.API_BASE_URL || '').replace(/\/$/, '');
    function csrfToken() {
        const part = document.cookie.split('; ').find(cookie => cookie.startsWith('csrf_token='));
        return part ? decodeURIComponent(part.slice('csrf_token='.length)) : '';
    }
    async function request(path, options = {}) {
        let response;
        try {
            response = await fetch(base + '/api' + path, {
                ...options, credentials: 'same-origin',
                headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}),
                    ...((options.method && !['GET', 'HEAD'].includes(options.method)) && csrfToken() ? { 'X-CSRF-Token': csrfToken() } : {}),
                    ...options.headers }
            });
        } catch (_) { throw new Error('Không thể kết nối máy chủ. Vui lòng thử lại.'); }
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            window.dispatchEvent(new CustomEvent('shop:unauthorized'));
        }
        if (!response.ok) {
            const error = new Error(data.error?.message || 'Có lỗi xảy ra. Vui lòng thử lại.');
            error.status = response.status;
            error.code = data.error?.code;
            error.fields = data.error?.fields || {};
            throw error;
        }
        return data;
    }
    const json = (method, path, body) => request(path, { method, body: JSON.stringify(body) });
    return {
        request,
        me: () => request('/auth/me'),
        register: (body) => json('POST', '/auth/register', body),
        login: (body) => json('POST', '/auth/login', body),
        logout: () => json('POST', '/auth/logout', {}),
        product: (slug) => request('/products/' + encodeURIComponent(slug)),
        cart: () => request('/cart'),
        addItem: (variant_id) => json('POST', '/cart/items', { variant_id, quantity: 1 }),
        changeItem: (id, quantity) => json('PATCH', '/cart/items/' + id, { quantity }),
        removeItem: (id) => request('/cart/items/' + id, { method: 'DELETE' }),
        coupon: (code) => json('POST', '/cart/coupon', { code }),
        order: (body) => json('POST', '/orders', body)
    };
})();
