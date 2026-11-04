/* Thanh ngang màu đen dưới navbar: chỉ xuất hiện dưới tab đang được hover/focus
   và biến mất khi rời khỏi navbar. JavaScript thuần (không thư viện), chỉ đo
   vị trí/độ rộng; hiệu ứng trượt hoàn toàn do CSS `transition` trong store.css.
   Không có tab "active" cố định: nếu có, vạch đen dưới tab đó sẽ đứng yên khi
   chuột chuyển sang Nam / Phụ kiện / Hàng mới.
   Không có JS thì navbar vẫn dùng được bình thường, chỉ thiếu thanh trượt. */
(function () {
    'use strict';

    var nav = document.querySelector('.header-nav');
    if (!nav) return;

    var indicator = nav.querySelector('.nav-indicator');
    var links = Array.prototype.slice.call(nav.querySelectorAll('.nav-link'));
    if (!indicator || links.length === 0) return;

    /* Tab đang được trỏ tới; null = không có vạch nào (trạng thái mặc định). */
    var currentLink = null;

    function moveTo(link) {
        if (!link) return;
        var navBox = nav.getBoundingClientRect();
        var box = link.getBoundingClientRect();
        indicator.style.width = box.width + 'px';
        indicator.style.transform = 'translateX(' + (box.left - navBox.left) + 'px)';
        indicator.style.opacity = '1';
        currentLink = link;
    }

    function hide() {
        currentLink = null;
        indicator.style.opacity = '0';
    }

    links.forEach(function (link) {
        link.addEventListener('mouseenter', function () { moveTo(link); });
        link.addEventListener('focus', function () { moveTo(link); });
    });

    /* Rời khỏi toàn bộ navbar (kể cả panel mega menu) thì vạch biến mất hẳn,
       không quay về một tab mặc định nào. */
    nav.addEventListener('mouseleave', hide);
    nav.addEventListener('focusout', function (event) {
        if (!nav.contains(event.relatedTarget)) hide();
    });
    window.addEventListener('resize', function () {
        if (currentLink) moveTo(currentLink);
    });

    hide();
})();
