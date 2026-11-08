/* Trang "Sổ địa chỉ": địa chỉ thật từ GET /api/account/addresses.
   - Thêm      : POST  /api/account/addresses
   - Sửa       : PATCH /api/account/addresses/<id>
   - Xóa       : DELETE /api/account/addresses/<id>
   - Mặc định  : POST  /api/account/addresses/<id>/default
   Tỉnh/phường lấy từ GET /api/provinces và /api/provinces/<mã>/wards.
   Chưa đăng nhập thì giữ dữ liệu mẫu trong HTML. */
(function () {
    'use strict';
    const { api, el, errorMessage } = FS;

    const grid = document.getElementById('address-grid');
    if (!grid) return;
    const $ = (id) => document.getElementById(id);
    const notice = $('address-notice');
    const panel = $('address-form-panel');
    const form = $('address-form');
    const provinceSel = $('addr-province');
    const wardSel = $('addr-ward');
    let provinces = [];
    let editingId = null;
    let defaultName = '';

    function show(text, ok) {
        notice.textContent = text || '';
        notice.hidden = !text;
        notice.classList.toggle('is-ok', !!ok);
    }

    // ---- Danh sách ---------------------------------------------------------------------
    function card(a) {
        const link = (text, fn) => el('a', { href: '#', class: 'link-underline', onclick: (e) => { e.preventDefault(); fn(); } }, text);
        const actions = [link('Chỉnh sửa', () => openForm(a)), link('Xóa', () => remove(a))];
        if (!a.is_default) actions.push(link('Đặt làm mặc định', () => makeDefault(a)));
        const kids = [];
        actions.forEach((x, i) => { if (i) kids.push('  '); kids.push(x); });
        return el('article', { class: 'address-card' },
            el('div', { class: 'row-between' }, el('h2', null, a.full_name),
                a.is_default ? el('span', { class: 'badge' }, 'Mặc định') : (a.label ? el('span', { class: 'badge' }, a.label) : null)),
            el('p', { class: 'muted' }, a.phone),
            el('p', { class: 'muted' }, a.street, el('br'), a.ward, el('br'), a.province),
            el('div', { class: 'mt-4' }, ...kids));
    }

    async function load() {
        const res = await api('GET', '/api/account/addresses');
        if (res.status === 401) {
            show('Bạn chưa đăng nhập nên đang xem dữ liệu mẫu. Đăng nhập để quản lý địa chỉ thật của bạn.');
            return false;
        }
        if (!res.ok) { show(errorMessage(res)); return false; }
        grid.replaceChildren(...(res.data.items.length
            ? res.data.items.map(card)
            : [el('p', { class: 'muted' }, 'Bạn chưa có địa chỉ nào. Bấm "Thêm địa chỉ mới" để thêm.')]));
        return true;
    }

    async function remove(a) {
        if (!window.confirm('Xóa địa chỉ này?')) return;
        const res = await api('DELETE', '/api/account/addresses/' + a.id);
        if (!res.ok) { show(errorMessage(res)); return; }
        show('Đã xóa địa chỉ.', true);
        load();
    }

    async function makeDefault(a) {
        const res = await api('POST', '/api/account/addresses/' + a.id + '/default');
        if (!res.ok) { show(errorMessage(res)); return; }
        show('Đã đặt làm địa chỉ mặc định.', true);
        load();
    }

    // ---- Form thêm / sửa ---------------------------------------------------------------
    async function ensureProvinces() {
        if (provinces.length) return;
        const res = await api('GET', '/api/provinces');
        if (res.ok) provinces = res.data.items;
        provinceSel.replaceChildren(el('option', { value: '' }, 'Chọn tỉnh / thành phố'),
            ...provinces.map((p) => el('option', { value: p.code }, p.name)));
    }

    // Tải phường/xã của tỉnh đang chọn; `selected` là tên phường cần chọn sẵn (khi sửa).
    async function loadWards(selected) {
        wardSel.replaceChildren(el('option', { value: '' }, 'Chọn phường / xã'));
        const code = provinceSel.value;
        if (code) {
            const res = await api('GET', '/api/provinces/' + encodeURIComponent(code) + '/wards');
            if (res.ok) res.data.items.forEach((w) => wardSel.append(el('option', { value: w.name }, w.name)));
        }
        if (selected) {
            if (!Array.from(wardSel.options).some((o) => o.value === selected)) wardSel.append(el('option', { value: selected }, selected));
            wardSel.value = selected;
        }
    }

    async function openForm(a) {
        await ensureProvinces();
        editingId = a ? a.id : null;
        $('address-form-title').textContent = a ? 'Chỉnh sửa địa chỉ' : 'Thêm địa chỉ mới';
        $('addr-label').value = a ? a.label || '' : '';
        $('addr-name').value = a ? a.full_name : defaultName;
        $('addr-phone').value = a ? a.phone : '';
        $('addr-street').value = a ? a.street : '';
        $('addr-default').checked = a ? a.is_default : false;
        $('addr-default').disabled = !!(a && a.is_default);
        const match = a ? provinces.find((p) => p.name === a.province) : null;
        provinceSel.value = match ? match.code : '';
        if (a && !match) {
            provinceSel.append(el('option', { value: '', selected: true }, a.province));
        }
        await loadWards(a ? a.ward : '');
        panel.hidden = false;
        $('addr-name').focus();
        panel.scrollIntoView({ block: 'nearest' });
    }

    function closeForm() { panel.hidden = true; editingId = null; }

    $('address-add').addEventListener('click', (e) => { e.preventDefault(); show(''); openForm(null); });
    $('address-cancel').addEventListener('click', closeForm);
    provinceSel.addEventListener('change', () => loadWards(''));

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const provinceOpt = provinceSel.options[provinceSel.selectedIndex];
        const body = {
            label: $('addr-label').value.trim() || null,
            full_name: $('addr-name').value.trim(),
            phone: $('addr-phone').value.trim(),
            province: provinceOpt ? provinceOpt.textContent.replace(/^Chọn .*/, '') : '',
            ward: wardSel.value,
            street: $('addr-street').value.trim(),
        };
        if (editingId === null) body.is_default = $('addr-default').checked;
        const res = editingId === null
            ? await api('POST', '/api/account/addresses', body)
            : await api('PATCH', '/api/account/addresses/' + editingId, body);
        if (!res.ok) { show(res.status === 401 ? 'Bạn cần đăng nhập để lưu địa chỉ.' : errorMessage(res)); return; }
        if (editingId !== null && $('addr-default').checked && !res.data.address.is_default) {
            await api('POST', '/api/account/addresses/' + editingId + '/default');
        }
        closeForm();
        show(editingId === null ? 'Đã thêm địa chỉ.' : 'Đã cập nhật địa chỉ.', true);
        load();
    });

    // ---- Khởi động ---------------------------------------------------------------------
    (async function init() {
        const me = await api('GET', '/api/auth/me');
        if (me.ok && me.data.user) {
            defaultName = me.data.user.full_name || '';
            const name = document.getElementById('account-name');
            if (name) name.textContent = defaultName;
        }
        load();
    })();
})();
