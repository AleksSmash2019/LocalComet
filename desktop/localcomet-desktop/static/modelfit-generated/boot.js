
function appendErrorBanner(title, details, position) {
  const banner = document.createElement('div');
  banner.style.cssText = 'color:red; background:white; position:fixed; z-index:9999; left:0; width:100%; padding:20px; font-size:16px;';
  banner.style[position] = '0';
  banner.textContent = title + ': ' + details;
  (document.body || document.documentElement).appendChild(banner);
}
window.onerror = function(msg, url, lineNo, columnNo, error) {
  const stack = error && error.stack ? error.stack : '';
  appendErrorBanner('Error', String(msg) + ' | Line: ' + String(lineNo) + ' | Col: ' + String(columnNo) + ' | Error obj: ' + stack, 'top');
  return false;
};
window.addEventListener('unhandledrejection', function(event) {
  appendErrorBanner('Unhandled Rejection', String(event.reason), 'bottom');
});



;

      (function () {
        var root = document.documentElement;
        var inter = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
        var mono = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
        var sheet = document.createElement('style');
        sheet.textContent =
          ':root{--font-sans:' + inter + ';--font-mono:' + mono + ';}' +
          "body{font-family:var(--font-sans)}" +
          "code,pre,kbd{font-family:var(--font-mono)}";
        document.head.appendChild(sheet);
        var applyFontVar = function (node) {
          if (!node || node.nodeType !== 1) return;
          var style = node.getAttribute && node.getAttribute('style');
          if (style && style.indexOf('Inter') !== -1) {
            node.setAttribute('style', style.split('Inter').join('var(--font-sans, ' + inter.split(',')[0] + ')'));
          }
        };
        var observer = new MutationObserver(function (mutations) {
          for (var i = 0; i < mutations.length; i += 1) {
            mutations[i].addedNodes.forEach(applyFontVar);
          }
        });
        if (document.head) observer.observe(document.head, { childList: true, subtree: true });
        if (document.body) observer.observe(document.body, { childList: true, subtree: true });
      })();
    
;

(function () {
  'use strict';
  var KEY = 'localcomet.ui.preferences.v1';
  function apply() {
    var raw = null;
    try { raw = window.localStorage ? window.localStorage.getItem(KEY) : null; } catch (e) { return; }
    if (!raw) return;
    var accent = null;
    try {
      var parsed = JSON.parse(raw);
      accent = parsed && typeof parsed.accentColor === 'string' ? parsed.accentColor : null;
    } catch (e) { return; }
    if (!accent || !/^#[0-9a-fA-F]{6}$/.test(accent)) return;
    function ch(value) { return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)]; }
    function lift(rgb, amount) { return rgb.map(function (c) { return Math.min(255, Math.round(c + (255 - c) * amount)); }); }
    var rgb = ch(accent.slice(1));
    var strong = lift(rgb, 0.28);
    var root = document.documentElement;
    root.style.setProperty('--mf-accent', rgb.join(' '));
    root.style.setProperty('--mf-accent-soft', strong.join(' '));
    root.style.setProperty('--mf-ok', rgb.join(' '));
  }
  apply();
  window.addEventListener('storage', function (event) { if (!event.key || event.key === KEY) apply(); });
})();
