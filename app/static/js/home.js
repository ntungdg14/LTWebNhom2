/* Trang chủ: lấy dữ liệu thật từ GET /api/home rồi thay phần mẫu trong HTML:
   - lưới "Mua sắm theo danh mục" (#home-categories)
   - lưới "Sản phẩm được yêu thích" (#home-featured, thẻ có nút trái tim)
   Nếu API lỗi thì giữ nguyên dữ liệu mẫu. */
(function () {
    'use strict';
    const { api, el, productCard } = FS;

    const cats = document.getElementById('home-categories');
    const featured = document.getElementById('home-featured');
    if (!cats && !featured) return;

    function categoryTile(c) {
        return el('a', { href: '/shop?category=' + encodeURIComponent(c.slug) },
            el('div', { class: 'media media-tile media-' + (c.tone || 'taupe') },
                // Ảnh danh mục: app/static/images/categories/<slug>.jpg; chưa có file thì giữ khối màu.
                el('img', {
                    src: '/static/images/categories/' + encodeURIComponent(c.slug) + '.jpg', alt: c.name, loading: 'lazy',
                    onload: (e) => e.target.parentNode.classList.add('has-img'),
                    onerror: (e) => e.target.remove(),
                }),
                el('span', { class: 'media-label' }, 'Ảnh sản phẩm')),
            el('span', null, c.name));
    }

    async function load() {
        const res = await api('GET', '/api/home');
        if (!res.ok) return;
        const data = res.data;
        if (cats && data.categories && data.categories.length) {
            cats.replaceChildren(...data.categories.map(categoryTile));
        }
        if (featured && data.featured && data.featured.length) {
            featured.replaceChildren(...data.featured.map((p) => productCard(p, 'h3')));
        }
    }

    load();
})();
