/* ============================================================
   SCHOOLHUB — SKELETON LOADERS
   Automatic tables/containers ke liye skeleton dikhata hai
   ============================================================ */

window.Skeleton = {
  tableRows(tbodyId, rows = 5, cols = 5) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    const rowHtml = Array.from({ length: cols }, () =>
      `<td><div class="skeleton" style="height:16px; width:${60 + Math.random() * 30}%;"></div></td>`
    ).join('');
    tbody.innerHTML = Array.from({ length: rows }, () =>
      `<tr>${rowHtml}</tr>`
    ).join('');
  },

  cards(containerId, count = 4) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = Array.from({ length: count }, () => `
      <div class="metric-card">
        <div class="skeleton" style="height:12px; width:40%; margin-bottom:12px;"></div>
        <div class="skeleton" style="height:32px; width:70%;"></div>
      </div>
    `).join('');
  },

  block(containerId, lines = 3) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = Array.from({ length: lines }, (_, i) =>
      `<div class="skeleton" style="height:14px; width:${100 - i * 15}%; margin-bottom:10px;"></div>`
    ).join('');
  }
};

/* ---------- AUTO-SKELETON FOR KNOWN CONTAINERS ---------- */
// Runs before data loads — shows skeleton until real data arrives.
document.addEventListener('DOMContentLoaded', () => {
  // Tables
  const tables = ['studentsTable', 'feesTable', 'attendanceTable', 'gradesTable',
                  'staffTable', 'staffAttendanceTable', 'staffSalaryTable',
                  'announcementsList', 'teacherActivityList'];
  tables.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id.includes('Table')) {
      const cols = el.closest('table')?.querySelectorAll('thead th').length || 5;
      Skeleton.tableRows(id, 4, cols);
    }
  });
});