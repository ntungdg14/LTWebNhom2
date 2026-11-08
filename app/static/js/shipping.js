(function () {
    "use strict";
    var city = document.getElementById("ship-city");
    var ward = document.getElementById("ship-ward");
    var fmt = function (n) { return n === 0 ? "Miễn phí" : n.toLocaleString("vi-VN") + "₫"; };

    if (city && ward) {
        city.addEventListener("change", function () {
            ward.innerHTML = '<option value="">Chọn phường / xã</option>';
            if (!city.value) return;
            fetch("/api/provinces/" + encodeURIComponent(city.value) + "/wards", { headers: { Accept: "application/json" } })
                .then(function (r) { return r.ok ? r.json() : { items: [] }; })
                .then(function (data) {
                    data.items.forEach(function (w) {
                        var o = document.createElement("option");
                        o.value = o.textContent = w.name;
                        ward.appendChild(o);
                    });
                });
        });
    }

    var total = document.getElementById("sum-total");
    var feeEl = document.getElementById("sum-fee");
    document.querySelectorAll('input[name="shipping"]').forEach(function (radio) {
        radio.addEventListener("change", function () {
            var fee = parseInt(radio.dataset.fee, 10) || 0;
            feeEl.textContent = fmt(fee);
            total.textContent = fmt(parseInt(total.dataset.subtotal, 10) + fee);
        });
    });
})();
