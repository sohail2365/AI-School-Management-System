/* ============================================================
   SCHOOLHUB — PROFILE DROPDOWN
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  const userSection = document.querySelector('.user-section');
  if (!userSection) return;

  const avatar = userSection.querySelector('.user-avatar');
  const userInfo = userSection.querySelector('.user-info');
  if (!avatar) return;

  // Wrap avatar + info in a clickable area
  const trigger = document.createElement('div');
  trigger.style.cssText = 'display:flex; align-items:center; gap:12px; cursor:pointer; padding:6px 10px; border-radius:12px; transition:background 0.2s;';
  trigger.addEventListener('mouseenter', () => trigger.style.background = 'var(--bg-secondary, #fbfaf7)');
  trigger.addEventListener('mouseleave', () => trigger.style.background = 'transparent');

  if (userInfo) {
    userInfo.parentNode.insertBefore(trigger, userInfo);
    trigger.appendChild(avatar);
    trigger.appendChild(userInfo);
  }

  // Chevron
  const chevron = document.createElement('i');
  chevron.setAttribute('data-lucide', 'chevron-down');
  chevron.style.cssText = 'width:16px;height:16px;color:var(--gray);transition:transform 0.2s;';
  trigger.appendChild(chevron);

  // Dropdown menu
  const menu = document.createElement('div');
  menu.className = 'profile-dropdown-menu';
  menu.style.cssText = `
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: white;
    border-radius: 12px;
    box-shadow: 0 12px 40px rgba(10, 90, 84, 0.18);
    border: 1px solid var(--border, #e6e8e5);
    min-width: 220px;
    padding: 8px;
    opacity: 0;
    transform: translateY(-8px) scale(0.96);
    pointer-events: none;
    transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
    z-index: 1000;
  `;
  menu.innerHTML = `
    <a href="#" onclick="return showProfileInfo()" class="pd-item" style="display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;color:var(--dark,#1a2b29);text-decoration:none;font-size:14px;transition:background 0.15s;">
      <i data-lucide="user" style="width:16px;height:16px;"></i> My Profile
    </a>
    <a href="#" onclick="return openSettings()" class="pd-item" style="display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;color:var(--dark,#1a2b29);text-decoration:none;font-size:14px;transition:background 0.15s;">
      <i data-lucide="settings" style="width:16px;height:16px;"></i> Settings
    </a>
    <a href="#" onclick="return showKeyboardShortcuts()" class="pd-item" style="display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;color:var(--dark,#1a2b29);text-decoration:none;font-size:14px;transition:background 0.15s;">
      <i data-lucide="keyboard" style="width:16px;height:16px;"></i> Shortcuts
      <span style="margin-left:auto;font-size:11px;color:var(--gray);background:var(--bg-secondary,#fbfaf7);padding:2px 6px;border-radius:4px;">?</span>
    </a>
    <div style="height:1px;background:var(--border,#e6e8e5);margin:6px 4px;"></div>
    <a href="#" onclick="return doLogout()" class="pd-item pd-logout" style="display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;color:#c4453b;text-decoration:none;font-size:14px;transition:background 0.15s;">
      <i data-lucide="log-out" style="width:16px;height:16px;"></i> Logout
    </a>
  `;

  // Make userSection position:relative
  userSection.style.position = 'relative';
  userSection.appendChild(menu);

  // Hover styles for items
  menu.querySelectorAll('.pd-item').forEach(item => {
    item.addEventListener('mouseenter', () => {
      item.style.background = item.classList.contains('pd-logout') ? 'rgba(196,69,59,0.08)' : 'var(--bg-secondary,#fbfaf7)';
    });
    item.addEventListener('mouseleave', () => item.style.background = 'transparent');
  });

  // Toggle
  let isOpen = false;
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    isOpen = !isOpen;
    menu.style.opacity = isOpen ? '1' : '0';
    menu.style.transform = isOpen ? 'translateY(0) scale(1)' : 'translateY(-8px) scale(0.96)';
    menu.style.pointerEvents = isOpen ? 'auto' : 'none';
    chevron.style.transform = isOpen ? 'rotate(180deg)' : 'rotate(0)';
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!userSection.contains(e.target) && isOpen) {
      isOpen = false;
      menu.style.opacity = '0';
      menu.style.transform = 'translateY(-8px) scale(0.96)';
      menu.style.pointerEvents = 'none';
      chevron.style.transform = 'rotate(0)';
    }
  });

  if (window.lucide) window.lucide.createIcons();

  // Actions
  window.showProfileInfo = function() {
    const name = localStorage.getItem('user_full_name') || localStorage.getItem('user_email') || 'User';
    const role = localStorage.getItem('user_role') || 'admin';
    showToast(`Signed in as ${name} (${role})`, 'info', 4000);
    return false;
  };
  window.openSettings = function() {
    if (typeof switchView === 'function') switchView('settings');
    return false;
  };
  window.showKeyboardShortcuts = function() {
    showToast('Shortcuts: ? = show help, / = search, Esc = close', 'info', 5000);
    return false;
  };
  window.doLogout = function() {
    if (typeof logout === 'function') logout();
    else window.location.href = 'login.html';
    return false;
  };
});