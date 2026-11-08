/* Luồng đặt hàng: giỏ hàng -> /checkout/shipping -> /checkout -> /order-success. Một file cho 3 trang
   (nhận biết bằng thuộc tính data-checkout-page của trang: shipping | payment | success).

   shipping : GET /api/auth/me, /api/account/addresses (điền sẵn nếu đã đăng nhập), /api/provinces, /api/provinces/<mã>/wards,
              /api/checkout/options (phương thức giao hàng + phí + ngày dự kiến), GET /api/cart?shipping_method=...
              Bấm "Tiếp tục" -> lưu thông tin vào sessionStorage rồi sang /checkout.
   payment  : /api/checkout/options (phương thức thanh toán), GET /api/cart, POST /api/orders (tạo đơn từ giỏ hiện tại)
              -> chuyển tới /order-success?code=<mã đơn>.
   success  : GET /api/orders/<mã>  (chủ đơn, hoặc khách vừa đặt trong cùng phiên).
   Giá, giảm giá, phí ship và tổng tiền luôn do server tính; trang chỉ hiển thị. Mã giảm giá được áp ở trang giỏ hàng. */
(function () {
    'use strict';
    const { api, el, money, errorMessage, fmtDay, fmtDateTime } = FS;

    const root = document.querySelector('[data-checkout-page]');
    if (!root) return;
    const page = root.dataset.checkoutPage;
    const $ = (id) => document.getElementById(id);

    const STORE_KEY = 'fs_checkout';   // thông tin giao hàng đã nhập ở bước 2
    const LAST_ORDER_KEY = 'fs_last_order';
    const PHONE_RE = /^(0|\+84)\d{9}$/;
    const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

    // sessionStorage có thể bị chặn (chế độ riêng tư): mọi thao tác đều bọc try/catch.
    const store = {
        get(key) { try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch (e) { return null; } },
        set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* bỏ qua */ } },
        remove(key) { try { sessionStorage.removeItem(key); } catch (e) { /* bỏ qua */ } },
    };

    // ------------------------------------------------------------------ tiện ích chung
    function notice(text, ok) {
        const box = $('checkout-notice');
        if (!box) return;
        box.replaceChildren();
        box.hidden = !text;
        box.classList.toggle('is-ok', !!ok);
        if (text) box.append(text);
        if (text) box.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function clearErrors(form) {
        notice('');
        form.querySelectorAll('.form-error').forEach((n) => n.remove());
        form.querySelectorAll('[aria-invalid]').forEach((n) => n.removeAttribute('aria-invalid'));
    }

    function fieldError(input, text) {
        if (!input) return false;
        input.setAttribute('aria-invalid', 'true');
        (input.closest('.field') || input.parentElement).append(el('p', { class: 'form-error' }, text));
        return true;
    }

    // "2026-11-04","2026-11-06" -> "04–06/11/2026" (khác tháng thì ghi đủ hai đầu)
    function dateRange(est) {
        if (!est || !est.from) return '';
        const [y1, m1, d1] = est.from.split('-');
        const [y2, m2, d2] = (est.to || est.from).split('-');
        if (est.from === est.to || !est.to) return `${d1}/${m1}/${y1}`;
        return y1 === y2 && m1 === m2 ? `${d1}–${d2}/${m1}/${y1}` : `${fmtDay(est.from)} – ${fmtDay(est.to)}`;
    }
    const dayRange = (days) => (days && days.length ? (days[0] === days[1] ? days[0] : days[0] + '–' + days[1]) + ' ngày làm việc' : '');
    const feeText = (fee) => (fee === 0 ? 'Miễn phí' : money(fee));

    // ----------------------------------------------- tóm tắt đơn (dùng cho giỏ và đơn đã đặt)
    // `source` là cart (items[].product.name...) hoặc order (items[].name...): chuẩn hóa về cùng một dạng dòng.
    function lineOf(item) {
        if (item.product) {
            return { name: item.product.name, slug: item.product.slug, image: item.product.image || {}, color: item.color.name, hex: item.color.hex,
                size: item.size, price: item.price, quantity: item.quantity, total: item.line_total, issue: item.issue };
        }
        return { name: item.name, slug: item.product_slug, image: { tone: item.tone }, color: item.color, hex: null,
            size: item.size, price: item.price, quantity: item.quantity, total: item.line_total, issue: null };
    }

    function summaryLine(item) {
        const l = lineOf(item);
        const media = l.image.url
            ? el('div', { class: 'media media-sm media-' + (l.image.tone || 'taupe') }, el('img', { src: l.image.url, alt: l.name, loading: 'lazy' }))
            : FS.placeholderMedia({ name: l.name, tone: l.image.tone, colors: l.hex ? [{ hex: l.hex }] : [] }, 'sm');
        return el('div', { class: 'order-line' }, media,
            el('div', { class: 'grow' },
                el('h3', null, l.slug ? el('a', { href: '/product?slug=' + encodeURIComponent(l.slug) }, l.name) : l.name),
                el('p', { class: 'meta' }, 'Size ' + l.size + ' | ' + l.color, el('br'), money(l.price) + ' × ' + l.quantity),
                l.issue ? el('p', { class: 'cart-issue', style: 'color:var(--red-600);font-size:0.75rem;margin:0.25rem 0 0;' }, l.issue) : null),
            el('span', null, money(l.total)));
    }

    // Vẽ phần tóm tắt (các id sum-*) từ giỏ hàng hoặc đơn hàng (cùng tên trường: subtotal, discount, coupon...).
    function renderSummary(data) {
        const items = data.items || [];
        const qty = items.reduce((n, i) => n + i.quantity, 0);
        $('sum-count').textContent = items.length + ' dòng sản phẩm · Tổng số lượng: ' + qty;
        $('sum-lines').replaceChildren(...items.map(summaryLine));
        $('sum-subtotal-label').textContent = 'Tạm tính (' + qty + ' sản phẩm)';
        $('sum-subtotal').textContent = money(data.subtotal);

        // Giỏ có đối tượng coupon {code, percent}; đơn chỉ có coupon_code.
        const code = data.coupon ? data.coupon.code : data.coupon_code;
        const row = $('sum-discount-row');
        row.hidden = !(code && data.discount > 0);
        if (!row.hidden) {
            $('sum-discount-label').textContent = 'Giảm giá · ' + code + (data.coupon && data.coupon.percent ? ' (' + data.coupon.percent + '%)' : '');
            $('sum-discount').textContent = '-' + money(data.discount);
        }
        $('sum-shipping').textContent = items.length ? feeText(data.shipping_fee) : '—';
        $('sum-total').textContent = money(data.total);
    }

    // ================================================================= BƯỚC 2: GIAO HÀNG
    async function initShipping() {
        const form = $('shipping-form');
        const submit = $('ship-submit');
        const provinceSel = $('ship-city');
        const wardSel = $('ship-ward');
        const methodsBox = $('ship-methods');
        const saved = store.get(STORE_KEY) || {};
        let provinces = [];
        let methods = [];
        let cart = null;
        let method = saved.shipping_method || 'standard';
        let loggedIn = false;

        const input = (id) => $(id);
        const selectedProvinceName = () => {
            const opt = provinceSel.options[provinceSel.selectedIndex];
            return opt && opt.value ? opt.textContent : '';
        };

        // ---- tỉnh / phường
        function fillProvinces() {
            provinceSel.replaceChildren(el('option', { value: '' }, 'Chọn tỉnh / thành phố'),
                ...provinces.map((p) => el('option', { value: p.code }, p.name)));
        }
        function setProvinceByName(name) {
            const match = provinces.find((p) => p.name === name);
            provinceSel.value = match ? match.code : '';
        }
        async function loadWards(selectedName) {
            wardSel.replaceChildren(el('option', { value: '' }, 'Chọn phường / xã'));
            const code = provinceSel.value;
            if (!code) return;
            const res = await api('GET', '/api/provinces/' + encodeURIComponent(code) + '/wards');
            if (!res.ok) return;
            res.data.items.forEach((w) => wardSel.append(el('option', { value: w.name }, w.name)));
            if (selectedName) wardSel.value = Array.from(wardSel.options).some((o) => o.value === selectedName) ? selectedName : '';
        }
        provinceSel.addEventListener('change', () => loadWards(''));

        // ---- phương thức giao hàng
        function renderMethods() {
            methodsBox.replaceChildren(...methods.map((m) => {
                const radio = el('input', { type: 'radio', name: 'shipping', value: m.id, checked: m.id === method });
                radio.addEventListener('change', () => { method = m.id; refreshCart(); });
                return el('label', { class: 'choice' },
                    el('span', { class: 'choice-left' }, radio, ' ' + m.name, el('br'),
                        el('small', null, 'Dự kiến nhận hàng: ' + dateRange(m.estimated_delivery) + ' · ' + dayRange(m.days))),
                    el('span', null, feeText(m.fee)));
            }));
        }

        async function refreshCart() {
            const res = await api('GET', '/api/cart?shipping_method=' + encodeURIComponent(method));
            if (!res.ok) { notice(errorMessage(res)); return; }
            cart = res.data.cart;
            renderSummary(cart);
            const blocked = cart.items.length === 0 || cart.has_issues;
            submit.disabled = blocked;
            if (cart.items.length === 0) {
                notice('');
                $('checkout-notice').append('Giỏ hàng của bạn đang trống. ', el('a', { href: '/shop', class: 'link-underline' }, 'Tiếp tục mua sắm'));
                $('checkout-notice').hidden = false;
            } else if (cart.has_issues) {
                notice('Một số sản phẩm trong giỏ không còn đủ hàng, vui lòng quay lại giỏ hàng để kiểm tra.');
            }
        }

        // ---- điền sẵn: ưu tiên dữ liệu đã nhập ở lần trước, sau đó tới tài khoản / địa chỉ mặc định
        async function prefill() {
            const contact = saved.contact || {};
            const addr = saved.address || {};
            let name = contact.full_name || '';
            let phone = contact.phone || '';
            let email = contact.email || '';
            let province = addr.province || '';
            let ward = addr.ward || '';
            let street = addr.street || '';

            const me = await api('GET', '/api/auth/me');
            const user = me.ok ? me.data.user : null;
            loggedIn = !!user;
            if (user) {
                name = name || user.full_name || '';
                phone = phone || user.phone || '';
                email = email || user.email || '';
                if (!saved.address) {
                    const list = await api('GET', '/api/account/addresses');
                    const def = list.ok ? (list.data.items || []).find((a) => a.is_default) || (list.data.items || [])[0] : null;
                    if (def) {
                        name = contact.full_name || def.full_name || name;
                        phone = contact.phone || def.phone || phone;
                        province = def.province; ward = def.ward; street = def.street;
                    }
                }
            } else {
                // Khách vãng lai không có "địa chỉ mặc định" để lưu.
                const box = $('ship-default');
                if (box) { box.checked = false; box.closest('label').hidden = true; }
            }
            input('ship-name').value = name;
            input('ship-phone').value = phone;
            input('ship-email').value = email;
            input('ship-address').value = street;
            if (saved.note) input('ship-note').value = saved.note;
            if (saved.save_as_default === false && $('ship-default')) $('ship-default').checked = false;
            setProvinceByName(province);
            await loadWards(ward);
        }

        // ---- gửi form
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            clearErrors(form);
            const v = {
                full_name: input('ship-name').value.trim(),
                phone: input('ship-phone').value.trim(),
                email: input('ship-email').value.trim(),
                street: input('ship-address').value.trim(),
                province: selectedProvinceName(),
                ward: wardSel.value,
            };
            let ok = true;
            const check = (cond, id, text) => { if (!cond) { fieldError(input(id), text); ok = false; } };
            check(v.full_name, 'ship-name', 'Vui lòng nhập họ và tên.');
            check(PHONE_RE.test(v.phone.replace(/[\s.\-()]/g, '')), 'ship-phone', 'Số điện thoại không hợp lệ.');
            check(EMAIL_RE.test(v.email), 'ship-email', 'Email không hợp lệ.');
            check(v.province, 'ship-city', 'Vui lòng chọn tỉnh / thành phố.');
            check(v.ward, 'ship-ward', 'Vui lòng chọn phường / xã.');
            check(v.street, 'ship-address', 'Vui lòng nhập địa chỉ cụ thể.');
            if (!ok) return;
            if (!cart || cart.items.length === 0 || cart.has_issues) { notice('Giỏ hàng trống hoặc có sản phẩm không còn đủ hàng.'); return; }

            const defBox = $('ship-default');
            store.set(STORE_KEY, {
                contact: { full_name: v.full_name, phone: v.phone, email: v.email },
                address: { province: v.province, ward: v.ward, street: v.street },
                shipping_method: method,
                note: input('ship-note').value.trim(),
                save_as_default: loggedIn && defBox ? defBox.checked : false,
            });
            location.href = '/checkout';
        });

        // ---- khởi động
        const [optRes, provRes] = await Promise.all([api('GET', '/api/checkout/options'), api('GET', '/api/provinces')]);
        if (provRes.ok) { provinces = provRes.data.items || []; fillProvinces(); }
        if (optRes.ok && optRes.data.shipping_methods.length) {
            methods = optRes.data.shipping_methods;
            if (!methods.some((m) => m.id === method)) method = methods[0].id;
            renderMethods();
        } else {
            notice(errorMessage(optRes) + ' Đang hiển thị dữ liệu mẫu.');
        }
        await prefill();
        await refreshCart();
    }

    // ================================================================ BƯỚC 3: THANH TOÁN
    const PAYMENT_INFO = {
        cod: { desc: 'Thanh toán bằng tiền mặt cho nhân viên giao hàng.', badge: 'COD' },
        vnpay: { desc: 'Quét mã QR hoặc thanh toán qua ứng dụng ngân hàng.', badge: 'VNPAY' },
        momo: { desc: 'Chuyển đến ứng dụng MoMo để xác nhận thanh toán.', badge: 'MoMo' },
        card: { desc: 'Visa, Mastercard, JCB · Xác thực an toàn qua 3D Secure.', badge: 'THẺ' },
    };

    async function initPayment() {
        const form = $('payment-form');
        const submit = $('pay-submit');
        const info = store.get(STORE_KEY);
        if (!info || !info.contact || !info.address) { location.replace('/checkout/shipping'); return; }
        let cart = null;
        let busy = false;
        const method = info.shipping_method || 'standard';

        const selectedPayment = () => {
            const radio = form.querySelector('input[name="payment"]:checked');
            return radio ? radio.value : 'cod';
        };

        function renderShipTo(methodInfo) {
            const c = info.contact;
            const a = info.address;
            $('pay-ship-to').replaceChildren(el('span', null,
                el('strong', null, c.full_name), ' · ' + c.phone, el('br'),
                a.street + ', ' + a.ward + ', ' + a.province, el('br'),
                c.email, el('br'),
                el('small', null, methodInfo
                    ? methodInfo.name + ' · Dự kiến ' + dateRange(methodInfo.estimated_delivery) + ' · ' + feeText(methodInfo.fee)
                    : 'Phương thức giao hàng: ' + method),
                info.note ? el('br') : null,
                info.note ? el('small', null, 'Ghi chú: ' + info.note) : null));
        }

        function renderPayments(list) {
            const box = $('pay-methods');
            box.replaceChildren(...list.map((m, i) => {
                const extra = PAYMENT_INFO[m.id] || { desc: '', badge: m.id.toUpperCase() };
                return el('label', { class: 'choice' },
                    el('span', { class: 'choice-left' },
                        el('input', { type: 'radio', name: 'payment', value: m.id, checked: i === 0 }), ' ' + m.name,
                        extra.desc ? el('br') : null, extra.desc ? el('small', null, extra.desc) : null),
                    el('span', null, extra.badge));
            }));
        }

        function paintSubmit() {
            submit.textContent = 'Đặt hàng · ' + money(cart ? cart.total : 0);
            submit.disabled = busy || !cart || cart.items.length === 0 || cart.has_issues;
        }

        // Lỗi từ server -> chuỗi dễ đọc, kèm đường dẫn quay lại sửa thông tin nếu lỗi nằm ở bước giao hàng.
        function showOrderError(res) {
            const err = (res.data && res.data.error) || {};
            const fields = err.fields || {};
            const text = Object.keys(fields).length ? Object.values(fields).join(' ') : errorMessage(res);
            const box = $('checkout-notice');
            notice(text);
            const shippingFields = ['full_name', 'phone', 'email', 'province', 'ward', 'street', 'note', 'shipping_method'];
            if (Object.keys(fields).some((k) => shippingFields.includes(k))) {
                box.append(' ', el('a', { href: '/checkout/shipping', class: 'link-underline' }, 'Sửa thông tin giao hàng'));
            } else if (err.code === 'cart_empty' || err.code === 'stock_issue' || err.code === 'out_of_stock' || err.code === 'invalid_coupon') {
                box.append(' ', el('a', { href: '/cart', class: 'link-underline' }, 'Quay lại giỏ hàng'));
            }
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (busy) return;
            notice('');
            const terms = $('pay-terms');
            if (!terms.checked) { notice('Bạn cần đồng ý với Điều khoản mua hàng và Chính sách bảo mật.'); return; }
            if (!cart || cart.items.length === 0 || cart.has_issues) { notice('Giỏ hàng trống hoặc có sản phẩm không còn đủ hàng.'); return; }
            busy = true;
            paintSubmit();
            const res = await api('POST', '/api/orders', {
                full_name: info.contact.full_name,
                phone: info.contact.phone,
                email: info.contact.email,
                province: info.address.province,
                ward: info.address.ward,
                street: info.address.street,
                note: info.note || null,
                shipping_method: method,
                payment_method: selectedPayment(),
                vat_invoice: $('pay-vat').checked,
                save_as_default: !!info.save_as_default,
                accept_terms: terms.checked,
            });
            if (!res.ok) { busy = false; paintSubmit(); showOrderError(res); return; }
            const code = res.data.order.code;
            store.remove(STORE_KEY);
            store.set(LAST_ORDER_KEY, code);
            location.href = '/order-success?code=' + encodeURIComponent(code);
        });

        const [optRes, cartRes] = await Promise.all([
            api('GET', '/api/checkout/options'),
            api('GET', '/api/cart?shipping_method=' + encodeURIComponent(method)),
        ]);
        const methodInfo = optRes.ok ? optRes.data.shipping_methods.find((m) => m.id === method) : null;
        renderShipTo(methodInfo);
        if (optRes.ok && optRes.data.payment_methods.length) renderPayments(optRes.data.payment_methods);
        if (!cartRes.ok) { notice(errorMessage(cartRes)); return; }
        cart = cartRes.data.cart;
        renderSummary(cart);
        paintSubmit();
        if (cart.items.length === 0) {
            notice('');
            $('checkout-notice').append('Giỏ hàng của bạn đang trống. ', el('a', { href: '/shop', class: 'link-underline' }, 'Tiếp tục mua sắm'));
            $('checkout-notice').hidden = false;
        } else if (cart.has_issues) {
            notice('Một số sản phẩm trong giỏ không còn đủ hàng, vui lòng quay lại giỏ hàng để kiểm tra.');
            $('checkout-notice').append(' ', el('a', { href: '/cart', class: 'link-underline' }, 'Quay lại giỏ hàng'));
        }
    }

    // ============================================================ BƯỚC 4: ĐẶT HÀNG THÀNH CÔNG
    async function initSuccess() {
        const content = $('ok-content');
        const empty = $('ok-empty');
        const code = new URLSearchParams(location.search).get('code') || store.get(LAST_ORDER_KEY);

        function fail(text) {
            content.hidden = true;
            empty.hidden = false;
            if (text) { const box = $('ok-notice'); box.textContent = text; box.hidden = false; }
        }
        if (!code) { fail(''); return; }

        const res = await api('GET', '/api/orders/' + encodeURIComponent(code));
        if (!res.ok) { fail(res.status === 404 ? 'Không tìm thấy đơn hàng ' + code + '.' : errorMessage(res)); return; }
        const o = res.data.order;
        store.set(LAST_ORDER_KEY, o.code);

        $('ok-email').textContent = o.contact.email;
        $('ok-code').textContent = '#' + o.code;
        $('ok-date').textContent = fmtDateTime(o.created_at).replace(' · ', ', ');
        const badge = $('ok-status');
        badge.textContent = o.status_label;
        badge.className = 'badge ' + (o.status === 'delivered' ? 'badge-ok' : o.status === 'cancelled' ? 'badge-danger' : 'badge-warn');

        $('ok-eta').textContent = o.estimated_delivery ? 'Dự kiến nhận hàng: ' + dateRange(o.estimated_delivery) : o.status_label;
        $('ok-ship-method').textContent = o.shipping_method_name + ' · ' + feeText(o.shipping_fee);
        $('ok-ship-info').replaceChildren(el('strong', null, o.contact.full_name), ' · ' + o.contact.phone, el('br'), o.address.full, el('br'), o.contact.email);
        $('ok-note').textContent = o.note ? 'Ghi chú: ' + o.note : '';
        $('ok-note').hidden = !o.note;

        const online = o.payment_method !== 'cod';
        $('ok-pay-info').replaceChildren(
            payLabel(o.payment_method), el('br'),
            online ? 'Số tiền cần thanh toán: ' + money(o.total) : 'Thanh toán ' + money(o.total) + ' cho nhân viên giao hàng.', el('br'),
            'Trạng thái: ' + (o.payment_status_label || ''));
        $('ok-pay-note').textContent = online
            ? 'Cổng thanh toán trực tuyến chưa được tích hợp nên đơn đang ở trạng thái chưa thanh toán. Freesion sẽ liên hệ để hướng dẫn bạn thanh toán.'
            : 'Bạn sẽ nhận được thông báo khi đơn hàng được bàn giao cho đơn vị vận chuyển.';

        renderSummary(o);
        $('ok-detail-link').href = '/account/orders/' + encodeURIComponent(o.code);
    }

    const PAY_LABELS = {
        cod: 'Thanh toán khi nhận hàng (COD)', vnpay: 'VNPAY / Thẻ ATM nội địa', momo: 'Ví điện tử MoMo', card: 'Thẻ quốc tế',
    };
    function payLabel(id) { return PAY_LABELS[id] || id; }

    // ----------------------------------------------------------------------- chạy đúng trang
    if (page === 'shipping') initShipping();
    else if (page === 'payment') initPayment();
    else if (page === 'success') initSuccess();
})();
