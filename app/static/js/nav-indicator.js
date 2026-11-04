/* Thanh ngang màu đen dưới navbar: trượt mượt mà theo nút đang được hover.
   JavaScript thuần (không thư viện), chỉ đo vị trí/độ rộng; hiệu ứng trượt
   hoàn toàn do CSS `transition: transform, width` trong layouts/store.css.
   Không có JS thì navbar vẫn dùng được bình thường, chỉ thiếu thanh trượt. */
(function () {
    'use strict';

    var nav = document.querySelector('.header-nav');
    if (!nav) return;

    var indicator = nav.querySelector('.nav-indicator');
    var links = Array.prototype.slice.call(nav.querySelectorAll('.nav-link'));
    if (!indicator || links.length === 0) return;

    var defaultLink = nav.querySelector('.nav-link.is-active') || links[0];

    function moveTo(link) {
        if (!link) return;
        var navBox = nav.getBoundingClientRect();
        var box = link.getBoundingClientRect();
        indicator.style.width = box.width + 'px';
        indicator.style.transform = 'translateX(' + (box.left - navBox.left) + 'px)';
        indicator.style.opacity = '1';
    }

    function reset() {
        moveTo(defaultLink);
    }

    links.forEach(function (link) {
        link.addEventListener('mouseenter', function () { moveTo(link); });
        link.addEventListener('focus', function () { moveTo(link); });
    });

    /* Rời khỏi toàn bộ navbar (kể cả panel mega menu) mới quay về tab mặc định */
    nav.addEventListener('mouseleave', reset);
    nav.addEventListener('focusout', function (event) {
        if (!nav.contains(event.relatedTarget)) reset();
    });
    window.addEventListener('resize', reset);

    reset();
})();
