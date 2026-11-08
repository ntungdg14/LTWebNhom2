/* Khung chat nổi kiểu Messenger của khách <-> shop: màn "Đoạn chat" (chỉ có shop Freesion) -> bấm vào để nhắn tin. Nối với:
     GET  /api/chat/conversation                 tin cuối + số tin chưa đọc (không đánh dấu đã đọc) cho dòng trong danh sách
     GET  /api/chat/unread                       số tin shop gửi chưa đọc (dùng luôn để biết đã đăng nhập chưa)
     GET  /api/chat/messages?limit=&after_id=    đọc tin (after_id = polling tin mới), tự đánh dấu đã đọc
     POST /api/chat/messages                     gửi {body, order_code?, product_slug?}
   Chưa có websocket nên dùng polling: 4 giây/lần khi đang mở khung chat, 20 giây/lần để cập nhật huy hiệu khi đóng.
   Trang có thể gắn ngữ cảnh bằng thuộc tính data-chat-order="<mã đơn>" / data-chat-product="<slug>"; mở khung chat bằng
   bất kỳ nút nào có thuộc tính data-chat-open. */
(function () {
    'use strict';
    const { api, el, fmtShort, timeAgo, errorMessage } = FS;

    const widget = document.getElementById('chat-widget');
    if (!widget) return;
    const $ = (id) => document.getElementById(id);
    const panel = $('chat-panel'), toggle = $('chat-toggle'), badge = $('chat-badge');
    const list = $('chat-messages'), form = $('chat-form'), input = $('chat-input'), context = $('chat-context');
    const listView = $('chat-list-view'), convView = $('chat-conv-view'), threads = $('chat-threads'), search = $('chat-search');

    const FAST = 4000, SLOW = 20000;
    const state = { open: false, view: 'list', tab: 'all', conv: null, loggedIn: null, lastId: 0, seen: new Set(), timer: null, dismissed: { order: false, product: false } };

    // ------------------------------------------------------------ hiển thị
    function setBadge(n) { badge.textContent = n > 99 ? '99+' : n; badge.hidden = !n; }
    function scrollDown() { list.scrollTop = list.scrollHeight; }

    function bubble(m) {
        const tags = [];
        if (m.order_code) tags.push(el('span', { class: 'chat-tag' }, 'Về đơn ', el('a', { href: '/account/orders/' + encodeURIComponent(m.order_code) }, '#' + m.order_code)));
        if (m.product) tags.push(el('span', { class: 'chat-tag' }, 'Về sản phẩm ', el('a', { href: '/product?slug=' + encodeURIComponent(m.product.slug) }, m.product.name)));
        return el('div', { class: 'chat-msg ' + (m.is_mine ? 'is-mine' : 'is-shop'), 'data-id': m.id },
            ...tags, el('p', { class: 'chat-bubble' }, m.body), el('span', { class: 'chat-time' }, (m.is_mine ? '' : 'Freesion · ') + fmtShort(m.created_at)));
    }

    function renderEmpty() {
        list.replaceChildren(el('div', { class: 'chat-empty' }, 'Xin chào! 👋', el('br'), 'Freesion có thể giúp gì cho bạn? Hãy nhắn câu hỏi về sản phẩm hoặc đơn hàng.'));
    }

    function loginPrompt() {
        return el('div', { class: 'chat-threads-empty' }, 'Vui lòng đăng nhập để nhắn tin với shop.', el('br'), el('a', { class: 'btn', href: '/login' }, 'Đăng nhập'));
    }

    function renderLoginPrompt() {
        showView('list');
        threads.replaceChildren(loginPrompt());
    }

    // ------------------------------------------------------------ màn danh sách "Đoạn chat"
    function showView(view) {
        state.view = view;
        listView.hidden = view !== 'list';
        convView.hidden = view !== 'conv';
    }

    function renderThreads() {
        if (!state.loggedIn) { threads.replaceChildren(loginPrompt()); return; }
        const conv = state.conv;
        const unread = conv ? conv.unread : 0;
        const last = conv && conv.last_message;
        const keyword = search.value.trim().toLowerCase();
        const visible = (!keyword || 'freesion'.includes(keyword)) && (state.tab === 'all' || unread > 0);
        if (!visible) {
            threads.replaceChildren(el('p', { class: 'chat-threads-empty' }, state.tab === 'unread' && !keyword ? 'Không có tin nhắn chưa đọc.' : 'Không tìm thấy đoạn chat nào.'));
            return;
        }
        const preview = last ? (last.is_mine ? 'Bạn: ' : '') + last.body : 'Bắt đầu cuộc trò chuyện với Freesion';
        threads.replaceChildren(el('button', { type: 'button', class: 'chat-thread' + (unread ? ' is-unread' : ''), onclick: openConversation },
            el('span', { class: 'chat-avatar', 'aria-hidden': 'true' }, 'F'),
            el('span', { class: 'chat-thread-text' },
                el('span', { class: 'chat-thread-name' }, 'Freesion'),
                el('span', { class: 'chat-thread-sub' },
                    el('span', { class: 'chat-thread-preview' }, preview),
                    last ? el('span', { class: 'chat-thread-time' }, '· ' + timeAgo(last.created_at)) : null)),
            unread ? el('span', { class: 'chat-thread-dot', 'aria-label': unread + ' tin chưa đọc' }) : null));
    }

    async function loadThreads() {
        const res = await api('GET', '/api/chat/conversation');
        if (res.status === 401) { state.loggedIn = false; renderThreads(); return; }
        if (res.ok) { state.conv = res.data.conversation; setBadge(state.conv ? state.conv.unread : 0); }
        renderThreads();
    }

    function append(messages) {
        const fresh = messages.filter((m) => !state.seen.has(m.id));
        if (!fresh.length) return;
        if (!state.seen.size) list.replaceChildren(); // bỏ lời chào khi đã có tin
        fresh.forEach((m) => { state.seen.add(m.id); state.lastId = Math.max(state.lastId, m.id); list.append(bubble(m)); });
        scrollDown();
    }

    // ------------------------------------------------------------ ngữ cảnh (đơn / sản phẩm đang xem)
    function pageContext() {
        const orderEl = document.querySelector('[data-chat-order]');
        const productEl = document.querySelector('[data-chat-product]');
        return {
            order: !state.dismissed.order && orderEl ? orderEl.dataset.chatOrder : null,
            product: !state.dismissed.product && productEl ? productEl.dataset.chatProduct : null,
        };
    }

    function renderContext() {
        const ctx = pageContext();
        const chips = [];
        if (ctx.order) chips.push(el('span', { class: 'chat-chip' }, 'Đơn #' + ctx.order, el('button', { type: 'button', 'aria-label': 'Bỏ đơn hàng', onclick: () => { state.dismissed.order = true; renderContext(); } }, '×')));
        if (ctx.product) chips.push(el('span', { class: 'chat-chip' }, 'Sản phẩm: ' + ctx.product, el('button', { type: 'button', 'aria-label': 'Bỏ sản phẩm', onclick: () => { state.dismissed.product = true; renderContext(); } }, '×')));
        context.replaceChildren(...chips);
        context.hidden = !chips.length;
    }

    // ------------------------------------------------------------ gọi API
    async function checkLogin() {
        const res = await api('GET', '/api/chat/unread');
        state.loggedIn = res.ok;
        if (res.ok) setBadge(state.open ? 0 : res.data.unread);
        return res;
    }

    async function loadInitial() {
        const res = await api('GET', '/api/chat/messages?limit=50');
        if (res.status === 401) { state.loggedIn = false; renderLoginPrompt(); return; }
        if (!res.ok) { list.replaceChildren(el('p', { class: 'chat-error' }, errorMessage(res))); return; }
        state.seen.clear();
        state.lastId = 0;
        if (!res.data.items.length) renderEmpty(); else { list.replaceChildren(); append(res.data.items); }
        setBadge(0);
    }

    async function poll() {
        if (document.hidden) return;
        if (state.open && state.loggedIn && state.view === 'conv') {
            const res = await api('GET', '/api/chat/messages?after_id=' + state.lastId);
            if (res.ok) { append(res.data.items); setBadge(0); }
        } else if (state.open && state.loggedIn) {
            await loadThreads();
        } else if (state.loggedIn) {
            await checkLogin();
        }
    }

    function schedule() {
        clearInterval(state.timer);
        if (state.loggedIn === false) return;
        state.timer = setInterval(poll, state.open ? FAST : SLOW);
    }

    // ------------------------------------------------------------ mở / đóng / gửi
    // direct = true: mở thẳng cuộc trò chuyện (nút data-chat-open); mặc định mở màn "Đoạn chat" như Messenger.
    async function openChat(direct) {
        state.open = true;
        panel.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        showView('list');
        await checkLogin();
        if (!state.loggedIn) { renderLoginPrompt(); return; }
        if (direct === true) { await openConversation(); return; }
        await loadThreads();
        schedule();
    }

    async function openConversation() {
        showView('conv');
        form.hidden = false;
        renderContext();
        await loadInitial();
        schedule();
        input.focus();
    }

    async function backToList() {
        showView('list');
        form.hidden = true;
        await loadThreads();
    }

    function closeChat() {
        state.open = false;
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        schedule();
    }

    async function send(event) {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        const ctx = pageContext();
        const payload = { body: text };
        if (ctx.order) payload.order_code = ctx.order;
        if (ctx.product) payload.product_slug = ctx.product;
        $('chat-send').disabled = true;
        const res = await api('POST', '/api/chat/messages', payload);
        $('chat-send').disabled = false;
        const old = list.querySelector('.chat-error');
        if (old) old.remove();
        if (!res.ok) {
            if (res.status === 401) { state.loggedIn = false; renderLoginPrompt(); return; }
            list.append(el('p', { class: 'chat-error' }, errorMessage(res)));
            scrollDown();
            return;
        }
        input.value = '';
        input.style.height = 'auto';
        append([res.data.message]);
        // gắn ngữ cảnh chỉ cho tin đầu tiên sau khi bấm gửi; các tin sau hỏi tiếp cùng chủ đề thì khỏi lặp lại
        state.dismissed.order = state.dismissed.product = true;
        renderContext();
    }

    toggle.addEventListener('click', () => (state.open ? closeChat() : openChat()));
    $('chat-close').addEventListener('click', closeChat);
    $('chat-list-close').addEventListener('click', closeChat);
    $('chat-back').addEventListener('click', backToList);
    search.addEventListener('input', renderThreads);
    document.querySelectorAll('[data-chat-tab]').forEach((tab) => tab.addEventListener('click', () => {
        state.tab = tab.dataset.chatTab;
        document.querySelectorAll('[data-chat-tab]').forEach((t) => {
            t.classList.toggle('is-active', t === tab);
            t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
        });
        renderThreads();
    }));
    form.addEventListener('submit', send);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 96) + 'px'; });
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-chat-open]') && !state.open) openChat(true);
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });

    window.FSChat = { open: () => openChat(true), close: closeChat };

    // Lúc tải trang: biết đã đăng nhập chưa + cập nhật huy hiệu tin chưa đọc.
    checkLogin().then(schedule);
})();
