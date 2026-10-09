/* ============================================================
   SCHOOLHUB — BULK ATTENDANCE REGISTER (self-contained)
   Add to teacher-dashboard.html and professional_dashboard.html:
   <script src="js/bulk-attendance.js"></script>
   ============================================================ */
(function() {
    'use strict';
    
    function ensureModalExists() {
        if (document.getElementById('bulkAttendanceModal')) return;
        const html = `
        <div class="modal" id="bulkAttendanceModal">
            <div class="modal-content modal-wide" style="max-width:820px;">
                <span class="modal-close" onclick="closeBulkAttendance()">✕</span>
                <div class="modal-header">📋 Bulk Attendance Register</div>
                
                <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px;">
                    <div class="form-group" style="flex:1; min-width:160px;">
                        <label>Class</label>
                        <select id="baClass" onchange="loadBulkAttendance()">
                            <option value="">Select Class</option>
                        </select>
                    </div>
                    <div class="form-group" style="flex:1; min-width:160px;">
                        <label>Date</label>
                        <select id="baDate" onchange="loadBulkAttendance()"></select>
                    </div>
                </div>
                
                <div id="baLockedBanner" style="display:none; padding:12px 16px; border-radius:10px; margin-bottom:14px; background:#FEF3C7; color:#92400E; font-weight:600; font-size:0.9rem;"></div>
                
                <div id="baContent" style="display:none;">
                    <div style="display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; align-items:center;">
                        <button class="btn btn-sm btn-success" onclick="bulkAllPresent()">✓ All Present</button>
                        <button class="btn btn-sm btn-danger" onclick="bulkAllAbsent()">✗ All Absent</button>
                        <input type="text" id="baSearch" placeholder="🔍 Search student..." oninput="filterBulkAttendance()" style="flex:1; min-width:180px; padding:8px 12px; border:1.5px solid var(--border); border-radius:10px; font-size:13px; background:var(--bg-primary); color:var(--dark);">
                    </div>
                    
                    <div class="table-responsive" style="max-height:400px; overflow-y:auto; border:1px solid var(--border); border-radius:10px;">
                        <table>
                            <thead>
                                <tr>
                                    <th style="width:80px;">Roll</th>
                                    <th>Name</th>
                                    <th style="width:140px; text-align:center;">Status</th>
                                </tr>
                            </thead>
                            <tbody id="baTableBody"></tbody>
                        </table>
                    </div>
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; flex-wrap:wrap; gap:10px;">
                        <div id="baSummary" style="font-weight:600; font-size:0.9rem;"></div>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-secondary" onclick="closeBulkAttendance()">Cancel</button>
                            <button class="btn btn-warning" id="baUnlockBtn" onclick="unlockBulkAttendance()" style="display:none; background:linear-gradient(135deg,#F59E0B,#D97706); color:#fff; border:none;">🔓 Unlock</button>
                            <button class="btn btn-primary" id="baSubmitBtn" onclick="submitBulkAttendance()">💾 Submit Attendance</button>
                        </div>
                    </div>
                </div>
                
                <div id="baEmpty" style="color:var(--gray); text-align:center; padding:30px;">
                    Class aur date select karein.
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', html);
    }
    
    let baStudents = [];
    let baClassName = null;
    let baDate = null;
    let baLocked = false;
    let baIsAdmin = false;
    
    function getLast7Days() {
        const days = [];
        const today = new Date();
        for (let i = 0; i < 7; i++) {
            const d = new Date(today);
            d.setDate(today.getDate() - i);
            const str = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
            const label = i === 0 ? ('Today (' + str + ')') : (i === 1 ? 'Yesterday' : str);
            days.push({ value: str, label: label });
        }
        return days;
    }
    
    async function populateClasses() {
        const sel = document.getElementById('baClass');
        if (sel.options.length > 1) return;
        try {
            let classes = await apiRequest('/students/classes-summary');
            // ✅ NEW: Agar teacher hai toh sirf assigned class dikhao
            const filter = window.__bulkAttendanceClassFilter;
            if (filter) {
                classes = classes.filter(c => c.class_name === filter);
            }
            sel.innerHTML = '<option value="">Select Class</option>' +
                classes.map(c => '<option value="' + c.class_name + '">Class ' + c.class_name + ' (' + c.student_count + ')</option>').join('');
            // ✅ Auto-select if only one class (teacher ke liye)
            if (filter && classes.length === 1) {
                sel.value = classes[0].class_name;
                setTimeout(() => loadBulkAttendance(), 150);
            }
        } catch (e) {
            console.error('Failed to load classes:', e);
        }
    }
    
    function populateDates() {
        const sel = document.getElementById('baDate');
        sel.innerHTML = getLast7Days().map(d => '<option value="' + d.value + '">' + d.label + '</option>').join('');
    }
    
    window.openBulkAttendance = async function() {
        ensureModalExists();
        populateDates();
        await populateClasses();
        baIsAdmin = ((localStorage.getItem('user_role') || '').toLowerCase() === 'admin');
        document.getElementById('bulkAttendanceModal').classList.add('show');
        document.getElementById('baContent').style.display = 'none';
        document.getElementById('baEmpty').style.display = 'block';
        document.getElementById('baLockedBanner').style.display = 'none';
        await loadBulkAttendance();
    };
    
    window.closeBulkAttendance = function() {
        const m = document.getElementById('bulkAttendanceModal');
        if (m) m.classList.remove('show');
    };
    
    window.loadBulkAttendance = async function() {
        const cn = document.getElementById('baClass').value;
        const dt = document.getElementById('baDate').value;
        if (!cn || !dt) {
            document.getElementById('baContent').style.display = 'none';
            document.getElementById('baEmpty').style.display = 'block';
            return;
        }
        baClassName = cn; baDate = dt;
        try {
            const data = await apiRequest('/attendance/register/' + encodeURIComponent(cn) + '/' + dt);
            baStudents = data.students || [];
            baLocked = data.is_locked || false;
            renderBulkAttendanceTable();
            document.getElementById('baContent').style.display = 'block';
            document.getElementById('baEmpty').style.display = 'none';
            
            const banner = document.getElementById('baLockedBanner');
            const unlockBtn = document.getElementById('baUnlockBtn');
            const submitBtn = document.getElementById('baSubmitBtn');
            
            if (baLocked && !baIsAdmin) {
                banner.style.display = 'block';
                banner.style.background = '#FEF3C7';
                banner.style.color = '#92400E';
                banner.textContent = '🔒 Ye attendance lock hai. Admin se unlock karwayein.';
                unlockBtn.style.display = 'none';
                submitBtn.disabled = true;
                submitBtn.textContent = '🔒 Locked';
            } else if (baLocked && baIsAdmin) {
                banner.style.display = 'block';
                banner.style.background = '#DBEAFE';
                banner.style.color = '#1E40AF';
                banner.textContent = '🔒 Locked. Admin ke tor par edit ya unlock kar sakte hain.';
                unlockBtn.style.display = 'inline-flex';
                submitBtn.disabled = false;
                submitBtn.textContent = '💾 Submit (Re-lock)';
            } else {
                banner.style.display = 'none';
                unlockBtn.style.display = 'none';
                submitBtn.disabled = false;
                submitBtn.textContent = '💾 Submit Attendance';
            }
        } catch (e) {
            console.error('Load register failed:', e);
            alert('Register load nahi ho saka: ' + (e.message || e));
        }
    };
    
    function renderBulkAttendanceTable() {
        const tbody = document.getElementById('baTableBody');
        if (baStudents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--gray);padding:20px;">Koi student nahi.</td></tr>';
        } else {
            const disabled = baLocked && !baIsAdmin;
            tbody.innerHTML = baStudents.map(s => 
                '<tr data-name="' + (s.name||'').toLowerCase() + '" data-roll="' + (s.roll_number||'').toLowerCase() + '">' +
                '<td>' + (s.roll_number || '-') + '</td>' +
                '<td>' + s.name + '</td>' +
                '<td style="text-align:center;">' +
                '<button class="ba-toggle" data-sid="' + s.student_id + '" onclick="toggleBulkStatus(' + s.student_id + ')" ' + (disabled ? 'disabled' : '') + 
                ' style="width:56px;height:34px;border-radius:20px;border:none;cursor:' + (disabled ? 'not-allowed' : 'pointer') + ';background:' + (s.is_present ? '#10B981' : '#EF4444') + ';color:#fff;font-size:16px;transition:all 0.15s;">' + (s.is_present ? '🟢' : '🔴') + '</button>' +
                '</td></tr>'
            ).join('');
        }
        updateBulkSummary();
    }
    
    window.toggleBulkStatus = function(sid) {
        if (baLocked && !baIsAdmin) return;
        const s = baStudents.find(x => x.student_id === sid);
        if (!s) return;
        s.is_present = !s.is_present;
        const btn = document.querySelector('button.ba-toggle[data-sid="' + sid + '"]');
        if (btn) {
            btn.style.background = s.is_present ? '#10B981' : '#EF4444';
            btn.textContent = s.is_present ? '🟢' : '🔴';
        }
        updateBulkSummary();
    };
    
    window.bulkAllPresent = function() {
        if (baLocked && !baIsAdmin) return;
        baStudents.forEach(s => s.is_present = true);
        renderBulkAttendanceTable();
    };
    
    window.bulkAllAbsent = function() {
        if (baLocked && !baIsAdmin) return;
        baStudents.forEach(s => s.is_present = false);
        renderBulkAttendanceTable();
    };
    
    window.filterBulkAttendance = function() {
        const q = (document.getElementById('baSearch').value || '').trim().toLowerCase();
        document.querySelectorAll('#baTableBody tr').forEach(tr => {
            const nm = tr.dataset.name || '';
            const rl = tr.dataset.roll || '';
            tr.style.display = (!q || nm.includes(q) || rl.includes(q)) ? '' : 'none';
        });
    };
    
    function updateBulkSummary() {
        const p = baStudents.filter(s => s.is_present).length;
        const a = baStudents.length - p;
        document.getElementById('baSummary').innerHTML =
            '✅ <span style="color:#10B981;">' + p + ' Present</span> &nbsp; ❌ <span style="color:#EF4444;">' + a + ' Absent</span> &nbsp; 📊 Total: ' + baStudents.length;
    }
    
    window.submitBulkAttendance = async function() {
        if (!baClassName || !baDate) return;
        if (baStudents.length === 0) { alert('Koi student nahi.'); return; }
        if (baLocked && !baIsAdmin) { alert('Attendance locked hai.'); return; }
        
        const p = baStudents.filter(s => s.is_present).length;
        const a = baStudents.length - p;
        const msg = 'Class ' + baClassName + ' — ' + baDate + '\n\n✅ Present: ' + p + '\n❌ Absent: ' + a + '\nTotal: ' + baStudents.length + '\n\nSubmit karein? (Submit hone par lock ho jayegi)';
        if (!confirm(msg)) return;
        
        const btn = document.getElementById('baSubmitBtn');
        btn.disabled = true; btn.textContent = 'Saving...';
        try {
            const result = await apiRequest('/attendance/bulk-submit', {
                method: 'POST',
                body: JSON.stringify({
                    class_name: baClassName,
                    date: baDate,
                    records: baStudents.map(s => ({ student_id: s.student_id, is_present: s.is_present, remarks: null })),
                }),
            });
            alert('✅ ' + result.total + ' records saved. Attendance lock ho gayi.');
            await loadBulkAttendance();
        } catch (e) {
            console.error('Submit failed:', e);
            alert('Submit fail: ' + (e.message || e));
        } finally {
            btn.disabled = false;
            btn.textContent = '💾 Submit Attendance';
        }
    };
    
    window.unlockBulkAttendance = async function() {
        if (!baIsAdmin) return;
        if (!baClassName || !baDate) return;
        if (!confirm('Class ' + baClassName + ' — ' + baDate + ' unlock karein?')) return;
        try {
            const r = await apiRequest('/attendance/unlock?class_name=' + encodeURIComponent(baClassName) + '&date_str=' + baDate, { method: 'POST' });
            alert('✅ ' + (r.message || 'Unlocked'));
            await loadBulkAttendance();
        } catch (e) {
            alert('Unlock fail: ' + (e.message || e));
        }
    };
    
    console.log('✅ Bulk attendance module loaded');
})();