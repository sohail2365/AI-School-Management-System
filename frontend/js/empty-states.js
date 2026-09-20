/* ============================================================
   SCHOOLHUB — EMPTY STATE HELPER
   ============================================================ */

window.showEmptyState = function(tbodyId, icon, title, message, buttonText, buttonAction) {
  const el = document.getElementById(tbodyId);
  if (!el) return;

  const isTbody = el.tagName === 'TBODY';
  const table = isTbody ? el.closest('table') : null;
  const wrapper = isTbody ? table.parentElement : el;

  // Remove any existing empty state
  const existing = wrapper.querySelector('.empty-state');
  if (existing) existing.remove();

  const html = `
    <div class="empty-state">
      <div class="empty-state-icon">
        <i data-lucide="${icon}"></i>
      </div>
      <h3>${title}</h3>
      <p>${message}</p>
      ${buttonText ? `<button class="btn btn-primary" onclick="${buttonAction}">${buttonText}</button>` : ''}
    </div>
  `;

  if (isTbody) {
    if (table) table.style.display = 'none';
    wrapper.insertAdjacentHTML('beforeend', html);
  } else {
    el.innerHTML = html;
  }
  if (window.lucide) window.lucide.createIcons();
};

/* ✅ NEW: Clear empty state and restore table display */
window.clearEmptyState = function(tbodyId) {
  const el = document.getElementById(tbodyId);
  if (!el) return;

  const isTbody = el.tagName === 'TBODY';
  const table = isTbody ? el.closest('table') : null;
  const wrapper = isTbody ? (table ? table.parentElement : null) : el;
  if (!wrapper) return;

  // Remove empty state
  const existing = wrapper.querySelector('.empty-state');
  if (existing) existing.remove();

  // Restore table display
  if (isTbody && table) {
    table.style.display = '';
  }
};