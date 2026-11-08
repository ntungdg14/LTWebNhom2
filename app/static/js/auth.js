/* Trang đăng nhập / đăng ký / quên mật khẩu: gửi form bằng fetch tới /api/auth/...
   - login-form    -> POST /api/auth/login           (xong chuyển tới ?next=... hoặc /account)
   - register-form -> POST /api/auth/register        (tự đăng nhập, chuyển tới /account)
   - forgot-form   -> POST /api/auth/forgot-password (Development có reset_token -> hiện luôn bước đặt lại)
   - reset-form    -> POST /api/auth/reset-password  (cũng mở bằng /forgot-password?token=...)
   Lỗi theo từng trường hiện ngay dưới ô nhập; lỗi chung hiện ở khung .form-alert. */
(function () {
    'use strict';
    const { api, el, errorMessage } = FS;

    // Chỉ cho chuyển tới đường dẫn nội bộ (chống open redirect).
    function nextUrl() {
        const next = new URLSearchParams(location.search).get('next') || '';
        return next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\') ? next : '/account';
    }

    function alertBox(form) {
        let box = form.querySelector('.form-alert');
        if (!box) {
            box = el('p', { class: 'form-alert', role: 'alert', hidden: true });
            form.prepend(box);
        }
        return box;
    }

    function clearErrors(form) {
        const box = alertBox(form);
        box.hidden = true;
        box.textContent = '';
        form.querySelectorAll('.form-error').forEach((n) => n.remove());
        form.querySelectorAll('.input[aria-invalid]').forEach((n) => n.removeAttribute('aria-invalid'));
    }

    function fieldError(input, text) {
        if (!input) return false;
        input.setAttribute('aria-invalid', 'true');
        const holder = input.closest('.field') || input.parentElement;
        holder.append(el('p', { class: 'form-error' }, text));
        return true;
    }

    // Khóa lỗi của API -> id ô nhập trong HTML.
    const FIELD_IDS = {
        email: 'email', password: 'password', full_name: 'full-name',
        confirm_password: 'password-confirmation',
    };

    function showApiError(form, res, idMap) {
        const fields = (res.data.error && res.data.error.fields) || {};
        let shown = false;
        Object.entries(fields).forEach(([key, text]) => {
            const input = form.querySelector('#' + (idMap[key] || key));
            shown = fieldError(input, text) || shown;
        });
        if (!shown) {
            const box = alertBox(form);
            box.textContent = errorMessage(res);
            box.hidden = false;
        }
    }

    function showMessage(form, text, ok) {
        const box = alertBox(form);
        box.textContent = text;
        box.classList.toggle('is-ok', !!ok);
        box.hidden = false;
    }

    // Khóa nút gửi trong lúc chờ để không bấm đúp.
    async function withBusy(form, work) {
        const button = form.querySelector('button[type="submit"]');
        if (form.dataset.busy) return;
        form.dataset.busy = '1';
        const label = button.textContent;
        button.disabled = true;
        button.textContent = 'Đang xử lý…';
        try { await work(); } finally {
            delete form.dataset.busy;
            button.disabled = false;
            button.textContent = label;
        }
    }

    // Nút con mắt ở ô mật khẩu: bấm để hiện / ẩn (xử lý ở một chỗ duy nhất, gắn vào nút).
    document.querySelectorAll('.password-toggle').forEach((btn) => {
        const input = document.getElementById(btn.dataset.target);
        if (!input) return;
        btn.addEventListener('click', () => {
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            btn.classList.toggle('is-visible', show);
            btn.setAttribute('aria-pressed', show ? 'true' : 'false');
            btn.setAttribute('aria-label', show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
            input.focus();
        });
    });

    const $ = (form, id) => form.querySelector('#' + id);

    // ------------------------------------------------------------ đăng nhập
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            clearErrors(loginForm);
            withBusy(loginForm, async () => {
                const res = await api('POST', '/api/auth/login', {
                    email: $(loginForm, 'email').value.trim(),
                    password: $(loginForm, 'password').value,
                    remember: $(loginForm, 'remember').checked,
                });
                if (res.ok) { location.href = nextUrl(); return; }
                showApiError(loginForm, res, FIELD_IDS);
            });
        });
    }

    // ------------------------------------------------------------- đăng ký
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            clearErrors(registerForm);
            const password = $(registerForm, 'password').value;
            const confirm = $(registerForm, 'password-confirmation').value;
            let invalid = false;
            if (password !== confirm) { fieldError($(registerForm, 'password-confirmation'), 'Mật khẩu xác nhận không khớp.'); invalid = true; }
            if (!$(registerForm, 'terms').checked) {
                const box = alertBox(registerForm);
                box.textContent = 'Bạn cần đồng ý với Điều khoản sử dụng và Chính sách bảo mật.';
                box.hidden = false;
                invalid = true;
            }
            if (invalid) return;
            withBusy(registerForm, async () => {
                const res = await api('POST', '/api/auth/register', {
                    full_name: $(registerForm, 'full-name').value.trim(),
                    email: $(registerForm, 'email').value.trim(),
                    password,
                    confirm_password: confirm,
                });
                if (res.ok) { location.href = nextUrl(); return; }
                showApiError(registerForm, res, FIELD_IDS);
            });
        });
    }

    // ----------------------------------------------- quên mật khẩu + đặt lại
    const forgotForm = document.getElementById('forgot-form');
    const resetForm = document.getElementById('reset-form');

    function openReset(token) {
        if (!resetForm) return;
        resetForm.dataset.token = token;
        resetForm.hidden = false;
        if (forgotForm) forgotForm.hidden = true;
        document.querySelectorAll('.forgot-intro').forEach((n) => { n.hidden = true; });
        $(resetForm, 'new-password').focus();
    }

    if (forgotForm) {
        forgotForm.addEventListener('submit', (e) => {
            e.preventDefault();
            clearErrors(forgotForm);
            withBusy(forgotForm, async () => {
                const res = await api('POST', '/api/auth/forgot-password', { email: $(forgotForm, 'email').value.trim() });
                if (!res.ok) { showApiError(forgotForm, res, FIELD_IDS); return; }
                showMessage(forgotForm, res.data.message, true);
                // Chưa có dịch vụ email: Development trả kèm token để thử luôn ngay trên trang.
                if (res.data.reset_token) openReset(res.data.reset_token);
            });
        });
    }

    if (resetForm) {
        const urlToken = new URLSearchParams(location.search).get('token');
        if (urlToken) openReset(urlToken);
        resetForm.addEventListener('submit', (e) => {
            e.preventDefault();
            clearErrors(resetForm);
            const password = $(resetForm, 'new-password').value;
            const confirm = $(resetForm, 'new-password-confirmation').value;
            if (password !== confirm) { fieldError($(resetForm, 'new-password-confirmation'), 'Mật khẩu xác nhận không khớp.'); return; }
            withBusy(resetForm, async () => {
                const res = await api('POST', '/api/auth/reset-password', {
                    token: resetForm.dataset.token || '', password, confirm_password: confirm,
                });
                if (!res.ok) {
                    showApiError(resetForm, res, { password: 'new-password', confirm_password: 'new-password-confirmation' });
                    return;
                }
                showMessage(resetForm, res.data.message, true);
                resetForm.querySelectorAll('.field, button[type="submit"]').forEach((n) => { n.hidden = true; });
            });
        });
    }
})();
