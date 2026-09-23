/* Move between work areas without leaving the document. */
(function () {
  var roles = {dashboard:'executive', insight:'executive', payroll:'payroll', onboarding:'onboarding'};
  var labels = {dashboard:'통합 대시보드', insight:'인원 분석', payroll:'급여 마감', onboarding:'온보딩',
                report:'월초 리포트', decision:'채택 근거', integrations:'시스템 연동'};
  var links = document.querySelectorAll('.workspace-nav a[href^="/#"]');
  function select(id, scroll) {
    if (!labels[id]) id = 'dashboard';
    if (roles[id]) {
      var input = document.querySelector('input[name="role"][value="' + roles[id] + '"]');
      if (input && !input.checked) {
        input.checked = true;
        input.dispatchEvent(new Event('change', {bubbles:true}));
      }
    }
    links.forEach(function (a) {
      if (a.getAttribute('href') === '/#' + id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    var crumb = document.querySelector('.workspace-topbar strong');
    if (crumb) crumb.textContent = '워크스페이스 / ' + labels[id];
    if (scroll) {
      var target = document.getElementById(id);
      if (target) target.scrollIntoView({behavior:'auto', block:'start'});
    }
  }
  links.forEach(function (a) {
    a.addEventListener('click', function (event) {
      event.preventDefault();
      var id = a.getAttribute('href').slice(2);
      history.pushState(null, '', '/#' + id);
      select(id, true);
    });
  });
  window.addEventListener('popstate', function () { select(location.hash.slice(1), true); });
  select(location.hash.slice(1), !!location.hash);
})();
