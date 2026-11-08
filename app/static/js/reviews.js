/* Trang chi tiết sản phẩm: nối khu vực "Đánh giá từ khách hàng" với
     GET    /api/products/<slug>/reviews?page=   thống kê sao + danh sách (phân trang)
     POST   /api/products/<slug>/reviews         gửi đánh giá (cần đăng nhập)
     PATCH  /api/reviews/<id>                    sửa đánh giá của mình
     DELETE /api/reviews/<id>                    xóa đánh giá của mình
     GET    /api/account/reviews                 biết mình đã đánh giá sản phẩm này chưa / đã nhận hàng chưa
   Slug lấy từ ?slug= trên URL, mặc định theo data-product-slug của trang. Nếu API lỗi, giữ dữ liệu mẫu. */
(function () {
    'use strict';
    const { api, el, stars, timeAgo, errorMessage } = FS;

    const root = document.querySelector('[data-product-slug]');
    const box = document.getElementById('reviews');
    if (!root || !box) return;
    const slug = new URLSearchParams(location.search).get('slug') || root.dataset.productSlug;
    root.dataset.chatProduct = slug; // chat.js gắn sản phẩm này vào tin nhắn

    const FIT = { 1: 'Rất chật', 2: 'Hơi chật', 3: 'Vừa vặn', 4: 'Hơi rộng', 5: 'Rất rộng' };
    const $ = (id) => document.getElementById(id);
    const avgText = (n) => String(n).replace('.', ',');
    const state = { page: 1, pages: 1, loggedIn: null, mine: null, pending: false, editing: false };

    // ------------------------------------------------------------ thống kê
    function renderSummary(s) {
        const total = s.count;
        const holder = $('review-summary');
        const bars = [5, 4, 3, 2, 1].map((n) => {
            const c = s.distribution[String(n)] || 0;
            return el('div', null, el('span', null, n + ' sao'), el('i', { style: 'width:' + (total ? Math.round((c / total) * 100) : 0) + '%' }), el('em', null, c));
        });
        holder.replaceChildren(
            el('strong', null, total ? avgText(s.average) : '–'),
            el('span', null, total ? stars(Math.round(s.average)) : '☆☆☆☆☆'),
            el('p', { class: 'muted' }, total + ' đánh giá'),
            s.fit_average ? el('p', { class: 'review-fit' }, 'Độ vừa vặn: ' + FIT[Math.round(s.fit_average)] + ' (' + avgText(s.fit_average) + '/5)') : null,
            el('div', { class: 'review-bars' }, ...bars));
        const head = $('product-rating');
        if (head) head.replaceChildren(total ? stars(Math.round(s.average)) + ' ' : '', total ? el('span', null, avgText(s.average)) : '', total ? ' · ' + total + ' đánh giá' : 'Chưa có đánh giá');
    }

    // ------------------------------------------------------------ danh sách
    function reviewCard(r) {
        const meta = [r.author_name, r.city, r.verified ? 'Đã mua hàng' : null, r.body_info].filter(Boolean).join(' · ');
        const tools = r.is_mine ? el('div', { class: 'review-tools' },
            el('button', { type: 'button', onclick: () => startEdit(r) }, 'Sửa'),
            el('button', { type: 'button', onclick: () => removeReview(r) }, 'Xóa')) : null;
        return el('article', { class: r.is_mine ? 'is-mine' : null },
            el('p', { class: 'eyebrow' }, stars(r.rating) + ' · ' + timeAgo(r.created_at) + (r.is_mine ? ' · Đánh giá của bạn' : '')),
            r.title ? el('h3', null, r.title) : null,
            el('p', { class: 'muted' }, r.body),
            r.fit ? el('p', { class: 'review-fit' }, 'Độ vừa vặn: ' + FIT[r.fit]) : null,
            el('p', { class: 'meta' }, meta),
            tools);
    }

    async function loadReviews(page, append) {
        const res = await api('GET', '/api/products/' + encodeURIComponent(slug) + '/reviews?page=' + page);
        if (!res.ok) return false;
        const d = res.data;
        state.page = d.page;
        state.pages = d.pages;
        renderSummary(d.summary);
        const cards = d.items.map(reviewCard);
        const list = $('review-list');
        if (append) list.append(...cards);
        else list.replaceChildren(...(cards.length ? cards : [el('p', { class: 'review-empty' }, 'Chưa có đánh giá nào. Hãy là người đầu tiên chia sẻ cảm nhận!')]));
        $('review-more').hidden = state.page >= state.pages;
        return true;
    }

    // ------------------------------------------------------------ form
    function starPicker(name, value) {
        const wrap = el('div', { class: 'star-picker', role: 'radiogroup', 'aria-label': 'Số sao' });
        for (let n = 5; n >= 1; n--) {
            wrap.append(
                el('input', { type: 'radio', name, id: 'star-' + n, value: n, checked: value === n }),
                el('label', { for: 'star-' + n, title: n + ' sao' }, '★'));
        }
        return wrap;
    }

    function renderForm() {
        const holder = $('review-form-box');
        if (state.loggedIn === false) {
            holder.replaceChildren(el('p', { class: 'review-login-hint' }, el('a', { class: 'link-underline', href: '/login' }, 'Đăng nhập'), ' để viết đánh giá cho sản phẩm này.'));
            return;
        }
        if (state.loggedIn === null) { holder.replaceChildren(); return; }
        if (state.mine && !state.editing) { holder.replaceChildren(); return; } // đã đánh giá: sửa/xóa ngay trên thẻ đánh giá

        const r = state.mine || {};
        const msg = el('p', { class: 'review-form-msg', role: 'alert' });
        const title = el('input', { class: 'input', id: 'rv-title', maxlength: 120, value: r.title || '', placeholder: 'Ví dụ: Form đẹp, vải mát' });
        const body = el('textarea', { class: 'input', id: 'rv-body', rows: 4, maxlength: 2000, placeholder: 'Chia sẻ cảm nhận về chất vải, form dáng, độ vừa vặn...' }, r.body || '');
        const fit = el('select', { class: 'input', id: 'rv-fit' }, el('option', { value: '' }, 'Không đánh giá'),
            ...[1, 2, 3, 4, 5].map((n) => el('option', { value: n, selected: r.fit === n }, FIT[n])));
        const info = el('input', { class: 'input', id: 'rv-info', maxlength: 120, value: r.body_info || '', placeholder: 'Ví dụ: 1m65 · 52kg · Size M' });
        const city = el('input', { class: 'input', id: 'rv-city', maxlength: 80, value: r.city || '', placeholder: 'Ví dụ: Hà Nội' });
        const picker = starPicker('rating', r.rating);
        const submit = el('button', { type: 'submit', class: 'btn' }, state.mine ? 'Lưu thay đổi' : 'Gửi đánh giá');

        const form = el('form', { class: 'review-form', id: 'review-form', novalidate: true },
            el('h3', null, state.mine ? 'Sửa đánh giá của bạn' : 'Viết đánh giá của bạn'),
            state.pending && !state.mine ? el('p', { class: 'muted' }, '✓ Bạn đã nhận sản phẩm này, đánh giá sẽ được gắn nhãn "Đã mua hàng".') : null,
            el('div', { class: 'field' }, el('label', null, 'Số sao *'), picker),
            el('div', { class: 'field' }, el('label', { for: 'rv-title' }, 'Tiêu đề'), title),
            el('div', { class: 'field' }, el('label', { for: 'rv-body' }, 'Nội dung *'), body),
            el('div', { class: 'review-form-row' },
                el('div', { class: 'field' }, el('label', { for: 'rv-fit' }, 'Độ vừa vặn'), fit),
                el('div', { class: 'field' }, el('label', { for: 'rv-info' }, 'Thông tin cơ thể'), info),
                el('div', { class: 'field' }, el('label', { for: 'rv-city' }, 'Thành phố'), city)),
            el('div', { class: 'review-form-actions' }, submit,
                state.mine ? el('button', { type: 'button', class: 'btn btn-ghost', onclick: () => { state.editing = false; renderForm(); } }, 'Hủy') : null, msg));

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const rating = Number((form.querySelector('input[name="rating"]:checked') || {}).value || 0);
            if (!rating) { msg.textContent = 'Vui lòng chọn số sao.'; return; }
            const payload = {
                rating, body: body.value, title: title.value.trim() || null,
                fit: fit.value ? Number(fit.value) : null, body_info: info.value.trim() || null, city: city.value.trim() || null,
            };
            submit.disabled = true;
            const res = state.mine
                ? await api('PATCH', '/api/reviews/' + state.mine.id, payload)
                : await api('POST', '/api/products/' + encodeURIComponent(slug) + '/reviews', payload);
            submit.disabled = false;
            if (!res.ok) { msg.textContent = errorMessage(res); return; }
            state.mine = res.data.review;
            state.editing = false;
            await loadReviews(1, false);
            renderForm();
        });
        holder.replaceChildren(form);
    }

    function startEdit(review) {
        state.mine = review;
        state.editing = true;
        renderForm();
        $('review-form-box').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    async function removeReview(review) {
        if (!window.confirm('Xóa đánh giá này?')) return;
        const res = await api('DELETE', '/api/reviews/' + review.id);
        if (!res.ok) { window.alert(errorMessage(res)); return; }
        state.mine = null;
        state.editing = false;
        await loadReviews(1, false);
        renderForm();
    }

    // ------------------------------------------------------------ khởi động
    async function init() {
        const [ok, account] = await Promise.all([loadReviews(1, false), api('GET', '/api/account/reviews')]);
        if (!ok) return; // sản phẩm không tồn tại / API lỗi: giữ dữ liệu mẫu, không hiện form
        if (account.status === 401) state.loggedIn = false;
        else if (account.ok) {
            state.loggedIn = true;
            state.mine = (account.data.items || []).find((r) => r.product.slug === slug) || null;
            state.pending = (account.data.pending || []).some((p) => p.slug === slug);
        }
        renderForm();
        if (new URLSearchParams(location.search).get('review') === '1' && $('review-form')) {
            $('review-form').scrollIntoView({ block: 'center' });
        }
    }

    $('review-more').addEventListener('click', () => loadReviews(state.page + 1, true));
    init();
})();
