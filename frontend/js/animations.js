/* ============================================================
   SCHOOLHUB — ANIMATIONS + AUTO ICON REPLACEMENT
   Har HTML file mein add karein (</body> se pehle):
   <script src="js/animations.js"></script>
   ============================================================ */

/* ---------- EMOJI → LUCIDE ICON MAP ---------- */
const EMOJI_ICON_MAP = {
  '📊': 'bar-chart-3',
  '👨‍🎓': 'graduation-cap',
  '🪪': 'id-card',
  '💰': 'wallet',
  '✅': 'check-circle-2',
  '📈': 'trending-up',
  '🧑‍🏫': 'users',
  '💬': 'message-circle',
  '📢': 'megaphone',
  '⚙️': 'settings',
  '⚙': 'settings',
  '🚪': 'log-out',
  '🕐': 'clock',
  '➕': 'plus',
  '🗑️': 'trash-2',
  '🗑': 'trash-2',
  '✏️': 'pencil',
  '🔑': 'key-round',
  '📱': 'smartphone',
  '🖨️': 'printer',
  '🖨': 'printer',
  '✨': 'sparkles',
  '🔍': 'search',
  '📥': 'download',
  '🧾': 'receipt',
  '📖': 'book-open',
  '🎓': 'graduation-cap',
  '💵': 'banknote',
  '📋': 'clipboard-list',
  '🔐': 'lock',
  '✍️': 'pen-line',
  '✍': 'pen-line',
  '👪': 'users-round',
  '🧑‍💻': 'laptop',
  '👨‍👩‍👧': 'users',
  '📝': 'file-text',
  '⬆️': 'upload',
  '⬆': 'upload',
  '🏫': 'school',
  '⏳': 'hourglass',
  '📄': 'file-text',
  '◐': 'circle-dot',
  '👁️': 'eye',
  '👁': 'eye',
  '👋': 'hand',
  '🎯': 'target',
  '🔔': 'bell',
  'ℹ️': 'info',
  'ℹ': 'info',
  '❌': 'x-circle',
  '📌': 'pin',
  '📎': 'paperclip',
  '🔗': 'link',
  '📅': 'calendar',
  '⏰': 'alarm-clock',
  '🌐': 'globe',
  '⭐': 'star',
  '💡': 'lightbulb',
  '🛠️': 'wrench',
  '🛠': 'wrench',
  '📦': 'package',
  '🖼️': 'image',
  '🖼': 'image',
  '📸': 'camera',
  '🎨': 'palette',
  '⚡': 'zap',
  '🔥': 'flame',
  '🌈': 'rainbow',
  '💎': 'gem',
};

/* ---------- REPLACE EMOJIS WITH ICON ELEMENTS ---------- */
function replaceEmojisWithIcons(root) {
  root = root || document.body;
  const emojis = Object.keys(EMOJI_ICON_MAP).sort((a, b) => b.length - a.length);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent) continue;
    const tag = parent.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') continue;
    if (parent.closest('[data-no-icon-replace]')) continue;
    if (!node.nodeValue || !node.nodeValue.trim()) continue;
    if (emojis.some(e => node.nodeValue.includes(e))) {
      textNodes.push(node);
    }
  }

  textNodes.forEach(textNode => {
    const parts = [];
    let remaining = textNode.nodeValue;
    let safety = 0;
    while (safety++ < 50) {
      let earliestIdx = Infinity;
      let earliestEmoji = null;
      for (const emoji of emojis) {
        const idx = remaining.indexOf(emoji);
        if (idx !== -1 && idx < earliestIdx) {
          earliestIdx = idx;
          earliestEmoji = emoji;
        }
      }
      if (earliestEmoji === null) break;
      if (earliestIdx > 0) {
        parts.push(document.createTextNode(remaining.substring(0, earliestIdx)));
      }
      const icon = document.createElement('i');
      icon.setAttribute('data-lucide', EMOJI_ICON_MAP[earliestEmoji]);
      icon.className = 'lucide-replaced';
      parts.push(icon);
      remaining = remaining.substring(earliestIdx + earliestEmoji.length);
    }
    if (remaining) parts.push(document.createTextNode(remaining));
    if (parts.length > 0) {
      const frag = document.createDocumentFragment();
      parts.forEach(p => frag.appendChild(p));
      textNode.parentNode.replaceChild(frag, textNode);
    }
  });
}

/* ---------- LUCIDE REFRESH ---------- */
function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    try { window.lucide.createIcons(); } catch (e) {}
  }
}

/* ---------- BUTTON RIPPLE (mouse position) ---------- */
document.addEventListener('mousemove', (e) => {
  const btn = e.target.closest && e.target.closest('.btn, button');
  if (btn) {
    const rect = btn.getBoundingClientRect();
    btn.style.setProperty('--x', `${e.clientX - rect.left}px`);
    btn.style.setProperty('--y', `${e.clientY - rect.top}px`);
  }
}, { passive: true });

/* ---------- NUMBER COUNT-UP ---------- */
function animateValue(el, endValue, duration = 1100, prefix = '', suffix = '') {
  if (!el) return;
  const startTime = performance.now();
  const isFloat = String(endValue).includes('.');
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
    const current = endValue * eased;
    el.textContent = prefix + (isFloat ? current.toFixed(1) : Math.round(current).toLocaleString()) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
  el.classList.add('updated');
  setTimeout(() => el.classList.remove('updated'), 800);
}

function enhanceMetricValues() {
  document.querySelectorAll('.metric-value').forEach(el => {
    if (el.dataset.animDone === 'true') return;
    const raw = el.textContent.trim();
    const match = raw.match(/^(Rs\.\s*)?([\d,.]+)(%?)$/);
    if (!match) return;
    const prefix = match[1] || '';
    const num = parseFloat(match[2].replace(/,/g, ''));
    const suffix = match[3] || '';
    if (isNaN(num) || num === 0) return;
    el.dataset.animDone = 'true';
    animateValue(el, num, 1100, prefix, suffix);
  });
}

/* ---------- TOAST NOTIFICATION ---------- */
function ensureToastContainer() {
  let c = document.querySelector('.toast-container');
  if (!c) {
    c = document.createElement('div');
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  return c;
}
function showToast(message, type = 'info', duration = 3500) {
  const container = ensureToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const iconMap = {
    success: 'check-circle-2',
    error:   'alert-circle',
    info:    'info',
  };
  toast.innerHTML = `<i data-lucide="${iconMap[type] || 'info'}"></i><span>${message}</span>`;
  container.appendChild(toast);
  refreshIcons();
  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
window.showToast = showToast;
window.enhanceMetricValues = enhanceMetricValues;

/* ---------- AUTO-REPLACE ON DOM READY ---------- */
function runAll() {
  replaceEmojisWithIcons(document.body);
  refreshIcons();
  setTimeout(enhanceMetricValues, 400);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', runAll);
} else {
  runAll();
}

/* ---------- OBSERVE DYNAMIC CONTENT (tables/modals) ---------- */
const knownEmojiRegex = new RegExp(
  Object.keys(EMOJI_ICON_MAP)
    .map(e => e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')
);
let mutTimer = null;
const observer = new MutationObserver((mutations) => {
  let shouldProcess = false;
  for (const m of mutations) {
    for (const n of m.addedNodes) {
      if (n.nodeType === 1 && knownEmojiRegex.test(n.textContent || '')) {
        shouldProcess = true;
        break;
      }
    }
    if (shouldProcess) break;
  }
  if (shouldProcess) {
    clearTimeout(mutTimer);
    mutTimer = setTimeout(() => {
      replaceEmojisWithIcons(document.body);
      refreshIcons();
      enhanceMetricValues();
    }, 80);
  }
});

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
} else {
  document.addEventListener('DOMContentLoaded', () => {
    observer.observe(document.body, { childList: true, subtree: true });
  });
}

/* ---------- RE-RUN ICONS WHEN TAB BECOMES VISIBLE ---------- */
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshIcons();
});