/* ============================================================
   SCHOOLHUB — DARK MODE TOGGLE
   Har HTML file mein add karein (</body> se pehle):
   <script src="js/dark-mode.js"></script>
   ============================================================ */

(function() {
  const STORAGE_KEY = 'schoolhub_theme';

  function getPreferredTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'dark') {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
    updateIcon(theme);
  }

  function updateIcon(theme) {
    const btn = document.getElementById('darkModeToggle');
    if (!btn) return;
    const icon = btn.querySelector('[data-lucide]');
    if (icon) {
      icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon');
      if (window.lucide) window.lucide.createIcons();
    }
    btn.setAttribute('title', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  }

  function toggleTheme() {
    const current = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  function createToggleButton() {
    if (document.getElementById('darkModeToggle')) return;
    const btn = document.createElement('button');
    btn.id = 'darkModeToggle';
    btn.className = 'dark-mode-toggle';
    btn.setAttribute('aria-label', 'Toggle dark mode');
    btn.innerHTML = `<i data-lucide="${document.body.classList.contains('dark-mode') ? 'sun' : 'moon'}" style="width:20px;height:20px;"></i>`;
    btn.addEventListener('click', toggleTheme);
    document.body.appendChild(btn);
    if (window.lucide) window.lucide.createIcons();
  }

  const initial = getPreferredTheme();
  if (initial === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  function init() {
    if (document.body) {
      document.body.classList.toggle('dark-mode', initial === 'dark');
    }
    createToggleButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();