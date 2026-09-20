/* ============================================================
   SCHOOLHUB — PASSWORD SHOW/HIDE
   ============================================================ */

window.togglePassword = function(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  const icon = btn.querySelector('[data-lucide]');
  if (icon) {
    icon.setAttribute('data-lucide', isPassword ? 'eye-off' : 'eye');
    if (window.lucide) window.lucide.createIcons();
  }
};