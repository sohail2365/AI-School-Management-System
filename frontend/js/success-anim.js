/* ============================================================
   SCHOOLHUB — SUCCESS ANIMATION
   Usage: showSuccess('Student saved!', 1200)
   ============================================================ */

window.showSuccess = function(message, duration = 1400) {
  const overlay = document.createElement('div');
  overlay.className = 'success-overlay';
  overlay.innerHTML = `
    <div style="text-align:center;">
      <div class="success-checkmark">
        <svg viewBox="0 0 52 52">
          <circle cx="26" cy="26" r="25"/>
          <path d="M14 27 l8 8 l16 -16"/>
        </svg>
      </div>
      ${message ? `<div style="margin-top:20px; color:#fff; font-weight:600; font-size:1rem; text-shadow:0 2px 8px rgba(0,0,0,0.3);">${message}</div>` : ''}
    </div>
  `;
  document.body.appendChild(overlay);
  setTimeout(() => {
    overlay.style.transition = 'opacity 0.3s ease';
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 300);
  }, duration);
};