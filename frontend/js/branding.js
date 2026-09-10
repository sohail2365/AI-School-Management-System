/*
 * ============================================================
 *  SCHOOLHUB — DEVELOPER / SYSTEM OWNER CREDIT
 * ============================================================
 *  Yeh footer har page ke neeche corner mein ek chhota credit
 *  dikhata hai. Har client ko dete waqt sirf neeche DI gayi
 *  BRANDING values badal dein — poore system mein khud update
 *  ho jayegi (ek hi file edit karni hai).
 *
 *  Agar kisi client ke liye credit HIDE karni ho (white-label),
 *  to SHOW_CREDIT ko false kar dein.
 * ============================================================
 */
const BRANDING = {
  SHOW_CREDIT: true,
  DEVELOPER_NAME: "Sohail",
  PHONE: "0300-0000000",          // <-- yahan apna number daalein
  TAGLINE: "System designed & developed by",
};

(function renderCredit() {
  if (!BRANDING.SHOW_CREDIT) return;

  const el = document.createElement("div");
  el.setAttribute("id", "dev-credit-footer");
  el.style.cssText = [
    "position:fixed",
    "bottom:6px",
    "right:10px",
    "z-index:9998",
    "font-family:Arial, sans-serif",
    "font-size:10px",
    "color:#94a3b8",
    "background:rgba(255,255,255,0.75)",
    "padding:2px 8px",
    "border-radius:6px",
    "pointer-events:none",
    "user-select:none",
    "line-height:1.3",
    "text-align:right",
  ].join(";");

  el.innerHTML =
    `${BRANDING.TAGLINE} <strong style="color:#64748b;">${BRANDING.DEVELOPER_NAME}</strong>` +
    (BRANDING.PHONE ? ` · ${BRANDING.PHONE}` : "");

  // Add once DOM is ready.
  if (document.body) {
    document.body.appendChild(el);
  } else {
    window.addEventListener("DOMContentLoaded", () => document.body.appendChild(el));
  }
})();
