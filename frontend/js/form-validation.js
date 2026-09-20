/* ============================================================
   SCHOOLHUB — REAL-TIME FORM VALIDATION
   (Skips password fields that have an eye-toggle button)
   ============================================================ */

(function() {
  function addValidationUI(input) {
    if (input.dataset.valUI === 'true') return;
    input.dataset.valUI = 'true';

    const wrap = input.parentElement;
    if (!wrap) return;
    wrap.style.position = 'relative';

    // Skip adding validation icon if this field already has a toggle button
    const hasToggle = wrap.classList.contains('has-toggle') ||
                      wrap.querySelector('.password-toggle-btn') ||
                      wrap.querySelector('[data-lucide="eye"], [data-lucide="eye-off"]');

    if (!hasToggle) {
      const icon = document.createElement('i');
      icon.className = 'validation-icon';
      icon.style.cssText = 'position:absolute; right:12px; top:50%; transform:translateY(-50%); pointer-events:none; opacity:0; transition:opacity 0.2s;';
      wrap.appendChild(icon);
    }

    const hint = document.createElement('div');
    hint.className = 'validation-hint';
    hint.style.cssText = 'font-size:12px; margin-top:4px; min-height:16px; color:var(--danger, #c4453b);';
    wrap.appendChild(hint);
  }

  function setValidationState(input, state, message) {
    const wrap = input.parentElement;
    if (!wrap) return;
    const icon = wrap.querySelector('.validation-icon');
    const hint = wrap.querySelector('.validation-hint');

    if (state === 'valid') {
      input.style.borderColor = '#1a8c5c';
      if (icon) {
        icon.setAttribute('data-lucide', 'check-circle-2');
        icon.style.color = '#1a8c5c';
        icon.style.opacity = '1';
        icon.style.width = '18px';
        icon.style.height = '18px';
      }
      if (hint) hint.textContent = '';
    } else if (state === 'invalid') {
      input.style.borderColor = '#c4453b';
      if (icon) {
        icon.setAttribute('data-lucide', 'x-circle');
        icon.style.color = '#c4453b';
        icon.style.opacity = '1';
        icon.style.width = '18px';
        icon.style.height = '18px';
      }
      if (hint) hint.textContent = message || '';
    } else {
      input.style.borderColor = '';
      if (icon) icon.style.opacity = '0';
      if (hint) hint.textContent = '';
    }
    if (window.lucide) window.lucide.createIcons();
  }

  function validateInput(input) {
    const val = input.value.trim();
    if (!val) { setValidationState(input, 'idle'); return; }

    if (input.type === 'email') {
      const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
      setValidationState(input, ok ? 'valid' : 'invalid',
        ok ? '' : 'Please enter a valid email');
    } else if (input.type === 'tel') {
      const ok = /^[\d+\-\s()]{7,}$/.test(val);
      setValidationState(input, ok ? 'valid' : 'invalid',
        ok ? '' : 'Please enter a valid phone');
    } else if (input.type === 'password') {
      const ok = val.length >= 8;
      setValidationState(input, ok ? 'valid' : 'invalid',
        ok ? '' : 'Password must be at least 8 characters');
    } else if (input.required && val.length > 0) {
      setValidationState(input, 'valid');
    }
  }

  function initValidation() {
    document.querySelectorAll('input[type="email"], input[type="tel"], input[type="password"], input[required]').forEach(input => {
      if (input.dataset.valInit === 'true') return;
      input.dataset.valInit = 'true';
      addValidationUI(input);
      input.addEventListener('input', () => validateInput(input));
      input.addEventListener('blur', () => validateInput(input));
    });
  }

  document.addEventListener('DOMContentLoaded', initValidation);

  const observer = new MutationObserver(() => initValidation());
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  }
})();