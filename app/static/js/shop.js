/* Trang Shop: danh sách sản phẩm thật từ GET /api/products (lọc, sắp xếp, "Xem thêm"),
   danh mục + số lượng từ `facets`, nhóm màu từ GET /api/colors.
   Bộ lọc nằm trên URL (?department=&cat=&color=&size=&price=&q=&sort=&is_new=1&sale=1) nên chia sẻ/tải lại được.
   Liên kết cũ dạng ?category=nu | nam | phu-kien | hang-moi | sale | <slug danh mục> vẫn dùng được.
   HTML chỉ có khung chờ (skeleton), không có dữ liệu mẫu; nếu API lỗi thì hiện thông báo lỗi. */
(function () {
    'use strict';
    const { api, el, errorMessage, productCard } = FS;

    const grid = document.getElementById('shop-grid');
    if (!grid) return;
    const $ = (id) => document.getElementById(id);
    const notice = $('shop-notice');
    const more = $('shop-more');
    const form = $('filter-form');
    const sortSelect = $('sort');

    const DEPARTMENTS = { nu: 'Nữ', nam: 'Nam', 'phu-kien': 'Phụ kiện' };
    const SIZES = ['S', 'M', 'L', 'XL', 'XXL', '28', '29', '30', '31'];
    const PRICES = {
        lt500: { label: 'Dưới 500.000₫', price_max: 499999 },
        mid: { label: '500.000₫ – 1.000.000₫', price_min: 500000, price_max: 1000000 },
        gt1000: { label: 'Trên 1.000.000₫', price_min: 1000001 },
    };
    const SORTS = ['featured', 'newest', 'price_asc', 'price_desc', 'bestseller'];

    const split = (v) => (v || '').split(',').map((x) => x.trim()).filter(Boolean);

    let state = readState();
    let facets = [];
    let colorFamilies = [];
    let page = 1;
    let pages = 0;
    let loading = false;
    let token = 0;

    // ---- Trạng thái <-> URL ---------------------------------------------------------------

    function readState() {
        const q = new URLSearchParams(window.location.search);
        const s = {
            department: DEPARTMENTS[q.get('department')] ? q.get('department') : '',
            cat: [], color: split(q.get('color')), size: split(q.get('size')).map((x) => x.toUpperCase()),
            price: PRICES[q.get('price')] ? q.get('price') : '', q: (q.get('q') || '').trim(),
            sort: SORTS.includes(q.get('sort')) ? q.get('sort') : 'featured',
            is_new: q.get('is_new') === '1', sale: q.get('sale') === '1',
        };
        q.getAll('cat').forEach((v) => s.cat.push(...split(v)));
        const legacy = q.get('category');
        if (legacy) {
            if (DEPARTMENTS[legacy]) s.department = legacy;
            else if (legacy === 'hang-moi') s.is_new = true;
            else if (legacy === 'sale') s.sale = true;
            else if (legacy !== 'tat-ca' && !s.cat.includes(legacy)) s.cat.push(legacy);
        }
        return s;
    }

    function writeUrl(push) {
        const q = new URLSearchParams();
        if (state.department) q.set('department', state.department);
        if (state.cat.length) q.set('cat', state.cat.join(','));
        if (state.color.length) q.set('color', state.color.join(','));
        if (state.size.length) q.set('size', state.size.join(','));
        if (state.price) q.set('price', state.price);
        if (state.q) q.set('q', state.q);
        if (state.sort !== 'featured') q.set('sort', state.sort);
        if (state.is_new) q.set('is_new', '1');
        if (state.sale) q.set('sale', '1');
        const url = window.location.pathname + (q.toString() ? '?' + q : '');
        window.history[push ? 'pushState' : 'replaceState'](null, '', url);
    }

    function apiQuery(pageNo) {
        const q = new URLSearchParams({ page: pageNo, per_page: 9, sort: state.sort });
        if (state.department) q.set('department', state.department);
        if (state.cat.length) q.set('category', state.cat.join(','));
        if (state.color.length) q.set('color', state.color.join(','));
        if (state.size.length) q.set('size', state.size.join(','));
        if (state.q) q.set('q', state.q);
        if (state.is_new) q.set('is_new', '1');
        if (state.sale) q.set('sale', '1');
        const p = PRICES[state.price];
        if (p && p.price_min !== undefined) q.set('price_min', p.price_min);
        if (p && p.price_max !== undefined) q.set('price_max', p.price_max);
        return q.toString();
    }

    // ---- Vẽ giao diện -------------------------------------------------------------------
    function showNotice(text) { notice.textContent = text || ''; notice.hidden = !text; }

    function heading() {
        let title = 'Tất cả sản phẩm';
        let current = 'Tất cả sản phẩm';
        if (state.sale) title = current = 'Ưu đãi';
        else if (state.is_new) title = current = 'Hàng mới về';
        else if (state.department) title = current = DEPARTMENTS[state.department];
        else if (state.cat.length === 1) {
            const f = facets.find((c) => c.slug === state.cat[0]);
            title = current = f ? f.name : 'Sản phẩm';
        }
        if (state.q) title = 'Kết quả cho "' + state.q + '"';
        $('shop-title').textContent = title;
        $('shop-current').textContent = current;
        document.title = title + ' - FREESION';
    }

    function renderFilters() {
        $('filter-categories').replaceChildren(...facets.map((c) => el('label', null,
            el('input', { type: 'checkbox', name: 'cat', value: c.slug, checked: state.cat.includes(c.slug) }),
            ' ' + c.name + ' (' + c.count + ')')));

        $('filter-colors').replaceChildren(...colorFamilies.map((f) => el('button', {
            type: 'button', class: 'color-swatch' + (state.color.includes(f.slug) ? ' is-active' : ''),
            style: 'background:' + f.hex, 'aria-label': f.name, 'aria-pressed': state.color.includes(f.slug) ? 'true' : 'false',
            title: f.name, 'data-color': f.slug,
        })));

        $('filter-sizes').replaceChildren(...SIZES.map((s) => el('button', {
            type: 'button', class: 'chip' + (state.size.includes(s) ? ' is-active' : ''), 'data-size': s,
            'aria-pressed': state.size.includes(s) ? 'true' : 'false',
        }, s)));

        $('filter-price').replaceChildren(
            el('label', null, el('input', { type: 'radio', name: 'price', value: '', checked: !state.price }), ' Tất cả mức giá'),
            ...Object.entries(PRICES).map(([key, p]) => el('label', null,
                el('input', { type: 'radio', name: 'price', value: key, checked: state.price === key }), ' ' + p.label)));

        sortSelect.value = state.sort;
    }

    function empty() {
        return el('div', { class: 'shop-empty' },
            el('p', { class: 'muted' }, 'Không có sản phẩm nào phù hợp với bộ lọc.'),
            el('button', { type: 'button', class: 'btn btn-ghost', onclick: () => { state = { department: '', cat: [], color: [], size: [], price: '', q: '', sort: 'featured', is_new: false, sale: false }; refresh(true); } }, 'Xóa bộ lọc'));
    }

    // ---- Tải dữ liệu --------------------------------------------------------------------
    async function load(append) {
        if (loading) return;
        loading = true;
        const mine = ++token;
        more.disabled = true;
        const res = await api('GET', '/api/products?' + apiQuery(append ? page + 1 : 1));
        loading = false;
        if (mine !== token) return;
        if (!res.ok) {
            showNotice(errorMessage(res));
            if (!append) grid.replaceChildren(el('div', { class: 'shop-empty' },
                el('p', { class: 'muted' }, 'Không tải được danh sách sản phẩm.'),
                el('button', { type: 'button', class: 'btn btn-ghost', onclick: () => load(false) }, 'Thử lại')));
            grid.removeAttribute('aria-busy');
            grid.classList.remove('is-loading');
            more.disabled = false;
            return;
        }
        showNotice('');
        const data = res.data;
        page = data.page;
        pages = data.pages;
        facets = (data.facets && data.facets.categories) || facets;
        const cards = data.items.map((p) => productCard(p, 'h2'));
        if (append) grid.append(...cards);
        else grid.replaceChildren(...(cards.length ? cards : [empty()]));
        grid.removeAttribute('aria-busy');
        grid.classList.remove('is-loading');
        $('shop-count').textContent = data.total + ' sản phẩm';
        more.hidden = page >= pages;
        more.disabled = false;
        renderFilters();
        heading();
    }

    function refresh(push) {
        writeUrl(push);
        renderFilters();
        heading();
        load(false);
    }

    function toggle(list, value) {
        const i = list.indexOf(value);
        if (i >= 0) list.splice(i, 1); else list.push(value);
    }

    // ---- Sự kiện ------------------------------------------------------------------------
    form.addEventListener('submit', (e) => { e.preventDefault(); });
    form.addEventListener('change', (e) => {
        if (e.target.name === 'cat') {
            state.cat = Array.from(form.querySelectorAll('input[name="cat"]:checked')).map((i) => i.value);
            if (state.cat.length) { state.is_new = false; state.sale = false; }
        } else if (e.target.name === 'price') {
            state.price = e.target.value;
        } else return;
        refresh(true);
    });
    form.addEventListener('click', (e) => {
        const swatch = e.target.closest('[data-color]');
        const chip = e.target.closest('[data-size]');
        if (swatch) toggle(state.color, swatch.dataset.color);
        else if (chip) toggle(state.size, chip.dataset.size);
        else return;
        refresh(true);
    });
    $('sort-form').addEventListener('submit', (e) => { e.preventDefault(); });
    sortSelect.addEventListener('change', () => { state.sort = sortSelect.value; refresh(true); });
    more.addEventListener('click', () => load(true));
    window.addEventListener('popstate', () => { state = readState(); refresh(false); });

    // ---- Khởi động ----------------------------------------------------------------------
    (async function init() {
        const res = await api('GET', '/api/colors');
        if (res.ok) colorFamilies = res.data.items || [];
        writeUrl(false);
        renderFilters();
        heading();
        load(false);
    })();
})();
