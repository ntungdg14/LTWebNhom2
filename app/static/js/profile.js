/* Trang "Tài khoản của bạn": hồ sơ thật từ GET /api/account/profile.
   - Lưu thay đổi : PATCH /api/account/profile
   - Cập nhật mật khẩu: POST /api/account/password
   Chưa đăng nhập thì giữ dữ liệu mẫu trong HTML và hiện thông báo. */
(function () {
    'use strict';
    const { api, errorMessage } = FS;

    const form = document.getElementById('profile-form');
    if (!form) return;
    const $ = (id) => document.getElementById(id);
    const pwForm = $('password-form');
    const notice = $('profile-notice');
    const pwNotice = $('password-notice');
    let user = null;

    function show(box, text, ok) {
        box.textContent = text || '';
        box.hidden = !text;
        box.classList.toggle('is-ok', !!ok);
    }

    function fill(u) {
        user = u;
        $('full-name').value = u.full_name || '';
        $('birth-date').value = u.birthday || '';
        $('gender').value = u.gender || 'nu';
        $('email').value = u.email || '';
        $('phone').value = u.phone || '';
        $('newsletter').checked = !!u.newsletter;
        const name = document.getElementById('account-name');
        if (name) name.textContent = u.full_name || '';
    }

    async function load() {
        const res = await api('GET', '/api/account/profile');
        if (res.status === 401) {
            show(notice, 'Bạn chưa đăng nhập nên đang xem dữ liệu mẫu. Đăng nhập để xem và sửa hồ sơ thật của bạn.');
            return;
        }
        if (!res.ok) { show(notice, errorMessage(res)); return; }
        show(notice, '');
        fill(res.data.user);
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const body = {
            full_name: $('full-name').value.trim(),
            birthday: $('birth-date').value || null,
            gender: $('gender').value,
            email: $('email').value.trim(),
            phone: $('phone').value.trim() || null,
            newsletter: $('newsletter').checked,
        };
        const res = await api('PATCH', '/api/account/profile', body);
        if (res.ok) { fill(res.data.user); show(notice, 'Đã lưu thay đổi.', true); }
        else show(notice, res.status === 401 ? 'Bạn cần đăng nhập để lưu thay đổi.' : errorMessage(res));
    });

    $('profile-reset').addEventListener('click', (e) => {
        e.preventDefault();
        if (user) { fill(user); show(notice, ''); } else load();
    });

    pwForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const res = await api('POST', '/api/account/password', {
            current_password: $('current-password').value,
            new_password: $('new-password').value,
            confirm_password: $('confirm-password').value,
        });
        if (res.ok) {
            pwForm.reset();
            show(pwNotice, res.data.message || 'Đã cập nhật mật khẩu.', true);
        } else {
            show(pwNotice, res.status === 401 ? 'Bạn cần đăng nhập để đổi mật khẩu.' : errorMessage(res));
        }
    });

    load();
})();
