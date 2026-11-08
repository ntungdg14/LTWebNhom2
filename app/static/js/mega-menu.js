/* Mega menu ở header: thay danh sách "Danh mục sản phẩm" mẫu bằng sản phẩm thật.
   Mỗi <ul data-mega-query="department=nu"> lấy GET /api/products?<query>&sort=bestseller&per_page=8
   (Nữ / Nam / Phụ kiện theo department, Hàng mới = is_new=1, Sale = sale=1). Chỉ gọi API lần đầu rê chuột / focus
   vào mục menu. Sản phẩm nổi bật (featured) có nhãn HOT. Bấm vào tên sẽ mở trang chi tiết sản phẩm.
   Nếu API lỗi hoặc chưa có sản phẩm thì giữ danh sách mẫu. */
(function () {
    'use strict';
    const { api, el } = FS;
    let hotSlugs = null;

    async function loadHot() {
        if (hotSlugs) return hotSlugs;
        const res = await api('GET', '/api/products?featured=1&per_page=48');
        hotSlugs = new Set(res.ok ? (res.data.items || []).map((p) => p.slug) : []);
        return hotSlugs;
    }

    async function fill(list) {
        if (list.dataset.loaded) return;
        list.dataset.loaded = '1';
        const [res, hot] = await Promise.all([
            api('GET', '/api/products?' + list.dataset.megaQuery + '&sort=bestseller&per_page=8'),
            loadHot(),
        ]);
        const items = res.ok ? (res.data.items || []) : [];
        if (!items.length) { delete list.dataset.loaded; return; }
        list.replaceChildren(...items.map((p) => el('li', null,
            el('a', { href: FS.productHref(p) }, p.name),
            hot.has(p.slug) ? el('span', { class: 'mega-hot' }, 'HOT') : null)));
    }

    document.querySelectorAll('.nav-item').forEach((item) => {
        const list = item.querySelector('[data-mega-query]');
        if (!list) return;
        const go = () => fill(list);
        item.addEventListener('mouseenter', go, { once: true });
        item.addEventListener('focusin', go, { once: true });
    });
})();
