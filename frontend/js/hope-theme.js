/* ============================================================
   HOPE-TO-SKILL MASTER THEME JS  —  v1.0.0
   Auto-applies theme enhancements on every page.
   Include with: <script src="js/hope-theme.js"></script>

   Version: v1.0.0   Last updated: 2026-09-24
   ============================================================ */

(function() {
    'use strict';

    // ==================== CONFIG ====================
    const THEME = {
        version: '1.0.0',
        storageKeys: {
            darkMode: 'schoolhub_dark_mode',
            bgOverlay: 'schoolhub_bg_overlay'
        },
        autoDetectLoginPage: true,
        autoInjectBackground: true
    };

    // ==================== UTILITY ====================
    function log(...args) {
        console.log('%c[HopeTheme]', 'color: #7C5CE0; font-weight: bold;', ...args);
    }

    // ==================== BACKGROUND PATTERN ====================
    function injectBackgroundPattern() {
        if (!THEME.autoInjectBackground) return;
        if (document.querySelector('.ht-bg-pattern')) return;

        const pattern = document.createElement('div');
        pattern.className = 'ht-bg-pattern';
        pattern.setAttribute('aria-hidden', 'true');
        pattern.innerHTML = `
            <div class="ht-float-icon ht-fi-1">📚</div>
            <div class="ht-float-icon ht-fi-2">🎓</div>
            <div class="ht-float-icon ht-fi-3">✏️</div>
            <div class="ht-float-icon ht-fi-4">📝</div>
            <div class="ht-float-icon ht-fi-5">🏫</div>
            <div class="ht-float-icon ht-fi-6">📖</div>
        `;

        // Insert as first child of body
        if (document.body.firstChild) {
            document.body.insertBefore(pattern, document.body.firstChild);
        } else {
            document.body.appendChild(pattern);
        }
    }

    // ==================== LOGIN PAGE AUTO-DETECT ====================
    function autoDetectLoginPage() {
        if (!THEME.autoDetectLoginPage) return;
        if (!document.body) return;
        if (document.body.classList.contains('hope-login-page')) return;
        if (document.body.classList.contains('hope-portal-page')) return;

        const path = (window.location.pathname || '').toLowerCase();
        const hash = (window.location.hash || '').toLowerCase();
        const loginPatterns = ['login', 'signin', 'sign-in', 'register', 'signup', 'sign-up', 'auth', 'index'];
        const isLoginPath = loginPatterns.some(p => path.includes(p) || hash.includes(p));

        // Also detect by content: page with a form but no sidebar/menu
        const hasSidebar = document.querySelector('.sidebar, .sidebar-menu, [data-view]');
        const hasLoginForm = document.querySelector('input[type="password"]');
        const looksLikeLogin = hasLoginForm && !hasSidebar;

        if (isLoginPath && looksLikeLogin) {
            document.body.classList.add('hope-login-page');
            log('Login page detected');
        }
    }

    // ==================== AUTO-DETECT PORTAL PAGES ====================
    function autoDetectPortalPage() {
        if (!document.body) return;
        if (document.body.classList.contains('hope-portal-page')) return;
        if (document.body.classList.contains('hope-login-page')) return;

        const hasSidebar = document.querySelector('.sidebar, .sidebar-menu, [data-view]');
        const hasTopHeader = document.querySelector('.top-header, .dashboard-header');
        if (hasSidebar || hasTopHeader) {
            document.body.classList.add('hope-portal-page');
            log('Portal page detected');
        }
    }

    // ==================== DARK MODE ====================
    function applySavedDarkMode() {
        try {
            const saved = localStorage.getItem(THEME.storageKeys.darkMode);
            if (saved === '1') {
                document.body.classList.add('dark-mode');
            }
        } catch (e) {
            console.warn('[HopeTheme] Could not read dark mode preference');
        }
    }

    function toggleDarkMode() {
        const enabled = !document.body.classList.contains('dark-mode');
        if (enabled) document.body.classList.add('dark-mode');
        else document.body.classList.remove('dark-mode');
        try {
            localStorage.setItem(THEME.storageKeys.darkMode, enabled ? '1' : '0');
        } catch (e) {}
        // Update icon if FAB exists
        const fabIcon = document.getElementById('darkModeFabIcon');
        if (fabIcon) fabIcon.textContent = enabled ? '☀️' : '🌙';
        return enabled;
    }

    // ==================== ANIMATED PAGE TITLE ====================
    function animatePageTitle(title) {
        const el = document.getElementById('pageTitle');
        if (!el) return;
        el.textContent = title;
        el.style.animation = 'none';
        void el.offsetWidth;
        el.style.animation = 'htTitleGradient 4s ease-in-out infinite';
    }

    // ==================== METRIC COUNT-UP ====================
    function animateMetricValue(elementId, targetValue, isCurrency) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const isNumeric = !isNaN(targetValue) && targetValue !== null && targetValue !== '';
        if (!isNumeric) { el.textContent = targetValue; return; }

        const end = parseFloat(targetValue);
        const duration = 800;
        const startTime = performance.now();
        const isCurrencyFlag = isCurrency === true;

        function tick(now) {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(0 + (end - 0) * eased);
            el.textContent = isCurrencyFlag ? 'Rs. ' + current.toLocaleString() : current.toLocaleString();
            if (progress < 1) requestAnimationFrame(tick);
            else el.textContent = isCurrencyFlag ? 'Rs. ' + end.toLocaleString() : end.toLocaleString();
        }
        requestAnimationFrame(tick);
    }

    // ==================== INIT ====================
    function init() {
        if (!document.body) {
            // DOM not ready yet — wait
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        // 1. Auto-detect page type
        autoDetectLoginPage();
        autoDetectPortalPage();

        // 2. Inject background pattern
        injectBackgroundPattern();

        // 3. Apply saved dark mode
        applySavedDarkMode();

        // 4. Add fade-in animation class to content if not present
        document.querySelectorAll('.view.active, .container, main, .main-content').forEach(el => {
            if (!el.classList.contains('ht-fade-in')) el.classList.add('ht-fade-in');
        });

        log('Theme v' + THEME.version + ' initialized');
    }

    // Run init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ==================== GLOBAL EXPORTS ====================
    window.HopeTheme = {
        version: THEME.version,
        toggleDarkMode,
        animatePageTitle,
        animateMetricValue,
        // Manual control helpers
        addLoginClass: () => document.body.classList.add('hope-login-page'),
        addPortalClass: () => document.body.classList.add('hope-portal-page')
    };

})();