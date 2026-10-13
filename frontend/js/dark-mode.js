/* ============================================================
   SCHOOLHUB — DARK MODE SYNC (smart, no duplicate buttons)
   Har HTML file mein add karein (</body> se pehle):
   <script src="js/dark-mode.js"></script>

   - Dashboard jaisi pages jinki apna FAB hai (#darkModeFabBtn):
     koi naya button nahi banega, sirf theme sync hogi.
   - Baaki pages: apna toggle button automatically banega.
   - Sab pages same storage key use karte hain → theme consistent.
   ============================================================ */

(function() {
  // ✅ Unified storage key — dashboard ke toggleDarkMode() se match karta hai
  const STORAGE_KEY = 'schoolhub_dark_mode';

  /* ---------- APPLY THEME ---------- */
  function applyTheme(enabled) {
    if (enabled) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }

    // Dashboard FAB icon sync (agar page par mojood hai)
    const fabIcon = document.getElementById('darkModeFabIcon');
    if (fabIcon) fabIcon.textContent = enabled ? '☀️' : '🌙';

    // Auto-generated button icon sync (baaki pages ke liye)
    const autoBtn = document.getElementById('darkModeToggle');
    if (autoBtn) {
      const icon = autoBtn.querySelector('[data-lucide]');
      if (icon) {
        icon.setAttribute('data-lucide', enabled ? 'sun' : 'moon');
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          try { window.lucide.createIcons(); } catch (e) {}
        }
      }
      autoBtn.setAttribute(
        'title',
        enabled ? 'Switch to light mode' : 'Switch to dark mode'
      );
    }
  }

  /* ---------- TOGGLE ---------- */
  function toggleTheme() {
    const isDark = document.body.classList.contains('dark-mode');
    const next = !isDark;
    localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
    applyTheme(next);
  }

  /* ---------- CREATE AUTO BUTTON (sirf jab zaroorat ho) ---------- */
  function createToggleButtonIfNeeded() {
    // Dashboard / pages with native FAB → skip
    if (document.getElementById('darkModeFabBtn')) return;
    // Agar pehle se koi button mojood hai → skip
    if (document.getElementById('darkModeToggle')) return;

    const btn = document.createElement('button');
    btn.id = 'darkModeToggle';
    btn.className = 'dark-mode-toggle';
    btn.setAttribute('aria-label', 'Toggle dark mode');

    const isDark = document.body.classList.contains('dark-mode');
    btn.innerHTML = `<i data-lucide="${isDark ? 'sun' : 'moon'}" style="width:20px;height:20px;"></i>`;
    btn.addEventListener('click', toggleTheme);

    document.body.appendChild(btn);

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      try { window.lucide.createIcons(); } catch (e) {}
    }
  }

  /* ---------- INIT ---------- */
  function init() {
    // Priority: localStorage → system preference
    const saved = localStorage.getItem(STORAGE_KEY);
    let enabled;

    if (saved === '1') {
      enabled = true;
    } else if (saved === '0') {
      enabled = false;
    } else {
      enabled = window.matchMedia('(prefers-color-scheme: dark)').matches;
      localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
    }

    applyTheme(enabled);
    createToggleButtonIfNeeded();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();