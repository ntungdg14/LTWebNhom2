/* Hộp thư của shop (trang /admin/messages), nối với:
     GET  /api/shop/chat/conversations?q=&unread=1&page=       danh sách hội thoại
     GET  /api/shop/chat/conversations/<id>/messages?after_id=  tin trong một hội thoại (tự đánh dấu đã đọc)
     POST /api/shop/chat/conversations/<id>/messages            trả lời {body}
     GET  /api/shop/chat/unread                                 tổng tin chưa đọc
   Chỉ tài khoản role = 'admin' mới dùng được (API trả 401 nếu chưa đăng nhập, 403 nếu không phải admin).
   Polling: danh sách 8 giây/lần, hội thoại đang mở 4 giây/lần. */
(function () {
    'use strict';
    const { api, el, fmtShort, timeAgo, errorMessage } = FS;

    const $ = (id) => document.getElementById(id);
    const listBox = $('msg-conversations'), body = $('msg-thread-body'), head = $('msg-thread-head');
    const reply = $('msg-reply'), input = $('msg-input'), notice = $('msg-notice');
    const state = { current: null, lastId: 0, seen: new Set(), q: '', unreadOnly: false, blocked: false };

    function showNotice(text, loginLink) {
        notice.replaceChildren(text, loginLink ? ' ' : '', loginLink ? el('a', { class: 'link-underline', href: '/login' }, 'Đăng nhập') : '');
        notice.hidden = !text;
    }

    function handleAuthError(res) {
        if (res.status === 401) showNotice('Bạn chưa đăng nhập. Hãy đăng nhập bằng tài khoản quản trị (role admin) để xem tin nhắn khách.', true);
        else if (res.status === 403) showNotice('Tài khoản hiện tại không phải quản trị viên nên không xem được tin nhắn khách.');
        else return false;
        state.blocked = true;
        listBox.replaceChildren(el('p', { class: 'muted' }, 'Không có quyền truy cập.'));
        return true;
    }

    // ------------------------------------------------------------ danh sách hội thoại
    function item(c) {
        const last = c.last_message;
        const preview = last ? (last.is_mine ? 'Bạn: ' : '') + last.body : 'Chưa có tin nhắn';
        return el('button', {
            type: 'button', class: 'msg-item' + (c.unread ? ' has-unread' : '') + (state.current && state.current.id === c.id ? ' is-active' : ''),
            onclick: () => openConversation(c),
        },
            el('div', { class: 'msg-item-top' }, el('strong', null, c.customer.full_name), c.unread ? el('span', { class: 'msg-unread' }, c.unread) : el('span', { class: 'msg-meta' }, timeAgo(c.last_message_at))),
            el('p', { class: 'msg-item-preview' }, preview));
    }

    async function loadList() {
        if (state.blocked) return;
        const params = new URLSearchParams();
        if (state.q) params.set('q', state.q);
        if (state.unreadOnly) params.set('unread', '1');
        const res = await api('GET', '/api/shop/chat/conversations?' + params);
        if (!res.ok) { if (!handleAuthError(res)) showNotice(errorMessage(res)); return; }
        showNotice('');
        listBox.replaceChildren(...(res.data.items.length ? res.data.items.map(item) : [el('p', { class: 'muted' }, 'Chưa có cuộc trò chuyện nào.')]));
        const total = await api('GET', '/api/shop/chat/unread');
        if (total.ok) $('msg-total').textContent = total.data.unread ? total.data.unread + ' tin nhắn chưa đọc' : 'Không có tin nhắn chưa đọc.';
    }

    // ------------------------------------------------------------ một hội thoại
    function row(m) {
        const tags = [];
        if (m.order_code) tags.push(el('span', { class: 'msg-tag' }, 'Về đơn ', el('a', { href: '/admin/orders/' + encodeURIComponent(m.order_code) }, '#' + m.order_code)));
        if (m.product) tags.push(el('span', { class: 'msg-tag' }, 'Về sản phẩm ', el('a', { href: '/product?slug=' + encodeURIComponent(m.product.slug) }, m.product.name)));
        return el('div', { class: 'msg-row ' + (m.sender === 'shop' ? 'is-shop' : 'is-customer') },
            ...tags, el('p', { class: 'msg-bubble' }, m.body),
            el('span', { class: 'msg-meta' }, fmtShort(m.created_at) + (m.sender === 'shop' ? (m.read ? ' · Khách đã xem' : ' · Đã gửi') : '')));
    }

    function append(messages) {
        const fresh = messages.filter((m) => !state.seen.has(m.id));
        if (!fresh.length) return;
        fresh.forEach((m) => { state.seen.add(m.id); state.lastId = Math.max(state.lastId, m.id); body.append(row(m)); });
        body.scrollTop = body.scrollHeight;
    }

    async function openConversation(c) {
        state.current = c;
        state.seen.clear();
        state.lastId = 0;
        head.replaceChildren(el('strong', null, c.customer.full_name), el('small', null, c.customer.email));
        body.replaceChildren();
        reply.hidden = false;
        const res = await api('GET', '/api/shop/chat/conversations/' + c.id + '/messages?limit=100');
        if (!res.ok) { if (!handleAuthError(res)) showNotice(errorMessage(res)); return; }
        append(res.data.items);
        input.focus();
        loadList();
    }

    async function pollThread() {
        if (!state.current || state.blocked || document.hidden) return;
        const res = await api('GET', '/api/shop/chat/conversations/' + state.current.id + '/messages?after_id=' + state.lastId);
        if (res.ok) append(res.data.items);
    }

    reply.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text || !state.current) return;
        $('msg-send').disabled = true;
        const res = await api('POST', '/api/shop/chat/conversations/' + state.current.id + '/messages', { body: text });
        $('msg-send').disabled = false;
        if (!res.ok) { showNotice(errorMessage(res)); return; }
        showNotice('');
        input.value = '';
        append([res.data.message]);
        loadList();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); reply.requestSubmit(); }
    });

    let searchTimer = null;
    $('msg-search').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { state.q = e.target.value.trim(); loadList(); }, 300);
    });
    $('msg-unread-only').addEventListener('change', (e) => { state.unreadOnly = e.target.checked; loadList(); });

    loadList();
    setInterval(() => { if (!document.hidden) loadList(); }, 8000);
    setInterval(pollThread, 4000);
})();
