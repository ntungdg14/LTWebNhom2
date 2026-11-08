(function () {
    'use strict';
    const api = window.ShopAPI;
    const next = new URLSearchParams(location.search).get('next');
    // Storage can be unavailable in private windows / embedded previews. Auth must still work.
    const storage = {
        get(key) { try { return sessionStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { sessionStorage.setItem(key, value); } catch (_) { /* optional notice */ } },
        remove(key) { try { sessionStorage.removeItem(key); } catch (_) { /* optional notice */ } }
    };
    function safeNext(value) {
        if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/';
        return value.startsWith('/login') || value.startsWith('/register') || value.startsWith('/api/') ? '/' : value;
    }
    function message(text) {
        let box = document.querySelector('.auth-form-message') || document.querySelector('#auth-notice');
        if (!box) {
            box = document.createElement('p'); box.id = 'auth-notice'; box.setAttribute('role', 'alert');
            document.querySelector('.site-main')?.prepend(box);
        }
        if (box) box.textContent = text;
    }
    let user = null;
    let ready = api.me().then(data => { user = data.user; draw(); return user; }).catch(() => { draw(); return null; });
    function draw() {
        document.querySelectorAll('[data-auth-guest]').forEach(el => { el.hidden = !!user; });
        document.querySelectorAll('[data-auth-user]').forEach(el => { el.hidden = !user; });
        document.querySelectorAll('[data-auth-name]').forEach(el => { el.textContent = 'Tài khoản'; el.title = user?.full_name || '';  });
    }
    function loginUrl(target = location.pathname + location.search) {
        return '/login?next=' + encodeURIComponent(safeNext(target));
    }
    function requireUser(target) {
        if (user) return true;
        storage.set('shop:notice', 'Vui lòng đăng nhập để tiếp tục');
        location.assign(loginUrl(target));
        return false;
    }
    document.addEventListener('click', async e => {
        const logout = e.target.closest('[data-logout]');
        if (logout) {
            e.preventDefault();
            if (logout.dataset.busy) return;
            logout.dataset.busy = '1';
            try { await api.logout(); user = null; draw(); location.assign('/'); }
            catch (err) { message(err.message); delete logout.dataset.busy; }
            return;
        }
        const guarded = e.target.closest('[data-require-auth]');
        if (guarded) {
            e.preventDefault();
            await ready;
            if (requireUser(guarded.getAttribute('href') || location.pathname + location.search)) {
                location.assign(guarded.getAttribute('href'));
            }
        }
    });
    window.addEventListener('shop:unauthorized', () => {
        if (!user) return;
        user = null; draw();
        storage.set('shop:notice', 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
        location.assign(loginUrl());
    });
    const notice = storage.get('shop:notice');
    if (notice) { message(notice); storage.remove('shop:notice'); }
    else if (next && location.pathname === '/login') message('Vui lòng đăng nhập để tiếp tục');
    const form = document.querySelector('[data-auth-form]');
    if (form) {
        ready.then(current => { if (current) location.replace(safeNext(next)); });
        form.addEventListener('submit', async e => {
            e.preventDefault();
            const button = form.querySelector('[type=submit]');
            if (button.disabled) return;
            const values = Object.fromEntries(new FormData(form));
            if (form.dataset.authForm === 'register') {
                if (!/[a-z]/.test(values.password) || !/[A-Z]/.test(values.password) || !/\d/.test(values.password)) {
                    message('Mật khẩu cần ít nhất 8 ký tự, gồm chữ hoa, chữ thường và số.'); return;
                }
                if (values.password !== values.confirm_password) { message('Mật khẩu xác nhận không khớp.'); return; }
                if (!values.terms) { message('Vui lòng đồng ý với điều khoản sử dụng.'); return; }
            }
            button.disabled = true; button.textContent = 'Đang xử lý…'; message('');
            try {
                const data = form.dataset.authForm === 'register'
                    ? await api.register({ full_name: values.full_name, email: values.email, password: values.password, confirm_password: values.confirm_password })
                    : await api.login({ email: values.email, password: values.password, remember: !!values.remember });
                user = data.user; draw();
                storage.set('shop:notice', form.dataset.authForm === 'register' ? 'Đăng ký thành công!' : 'Đăng nhập thành công!');
                location.assign(safeNext(next));
            } catch (err) {
                message(err.fields && Object.values(err.fields)[0] || err.message);
                button.disabled = false;
                button.textContent = form.dataset.authForm === 'register' ? 'Tạo tài khoản' : 'Đăng nhập';
            }
        });
    }
    document.querySelectorAll('[data-auth-switch]').forEach(link => { link.href += next ? '?next=' + encodeURIComponent(safeNext(next)) : ''; });
    window.ShopAuth = { ready, requireUser, message, get user() { return user; } };
})();
