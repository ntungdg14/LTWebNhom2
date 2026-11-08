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

    window.addEventListener('resize', reset);

    reset();
})();