// ============================================================
// main.js — StudyPlan client-side utilities
// ============================================================

/* ── DARK MODE ───────────────────────────────────── */

/**
 * Apply a theme ('light' | 'dark') to the document root
 * and persist it in localStorage.
 */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  const icon = document.getElementById("themeIcon");
  if (icon) {
    icon.className = theme === "dark"
      ? "bi bi-sun-fill"
      : "bi bi-moon-stars-fill";
  }
}

/** Toggle between light and dark. */
function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
}

// Restore saved theme on every page load (before paint to avoid flash)
(function initTheme() {
  const saved = localStorage.getItem("theme") || "light";
  applyTheme(saved);
})();


/* ── PASSWORD VISIBILITY TOGGLE ─────────────────── */

/**
 * Toggle the visibility of a password input.
 * @param {string} inputId — the input element's id
 */
function togglePwd(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isText = input.type === "text";
  input.type = isText ? "password" : "text";

  // Try to find the icon inside the nearest .pwd-toggle button
  const btn  = input.parentElement?.querySelector(".pwd-toggle i");
  if (btn) btn.className = isText ? "bi bi-eye" : "bi bi-eye-slash";
}


/* ── AUTO-DISMISS ALERTS ─────────────────────────── */

/**
 * Fade out and remove .alert-custom elements after a delay.
 */
(function autoDismiss() {
  const alerts = document.querySelectorAll(".alert-custom");
  alerts.forEach(el => {
    setTimeout(() => {
      el.style.transition = "opacity .5s ease";
      el.style.opacity    = "0";
      setTimeout(() => el.remove(), 500);
    }, 4500);   // 4.5 s visible
  });
})();


/* ── FORM VALIDATION HELPERS ─────────────────────── */

/**
 * Lightweight client-side validation for the Add Subject form.
 * Prevents obviously bad submissions before they hit Flask.
 */
(function setupFormValidation() {
  const form = document.getElementById("addForm");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    const name  = form.querySelector('[name="name"]');
    const hours = form.querySelector('[name="hours_per_day"]');

    if (!name?.value.trim()) {
      e.preventDefault();
      showInlineError(name, "Subject name cannot be empty.");
      return;
    }
    const h = parseFloat(hours?.value);
    if (isNaN(h) || h < 0.5 || h > 12) {
      e.preventDefault();
      showInlineError(hours, "Hours must be between 0.5 and 12.");
    }
  });
})();

/**
 * Show a temporary inline validation message beneath an input.
 * @param {HTMLElement} el
 * @param {string}      msg
 */
function showInlineError(el, msg) {
  // Remove any existing inline error for this element
  el.parentElement.querySelector(".inline-err")?.remove();

  const span       = document.createElement("span");
  span.className   = "inline-err";
  span.style.color = "var(--red)";
  span.style.fontSize = ".8rem";
  span.textContent = msg;
  el.parentElement.after(span);
  el.focus();

  setTimeout(() => span.remove(), 3000);
}


/* ── SUBJECT LIST SEARCH ─────────────────────────── */
// (Optional bonus: live search/filter if many subjects)
(function setupSubjectSearch() {
  const list = document.getElementById("subjectList");
  if (!list) return;

  // Inject a search box above the list if there are 5+ subjects
  const items = list.querySelectorAll(".subject-item");
  if (items.length < 5) return;

  const wrapper   = document.createElement("div");
  wrapper.style.marginBottom = ".75rem";

  const input     = document.createElement("input");
  input.type      = "text";
  input.placeholder = "Filter subjects…";
  input.className = "form-ctrl";
  input.style.marginBottom = ".5rem";

  wrapper.appendChild(input);
  list.parentElement.insertBefore(wrapper, list);

  input.addEventListener("input", () => {
    const q = input.value.toLowerCase();
    items.forEach(item => {
      const text = item.querySelector(".subject-name")?.textContent.toLowerCase() || "";
      item.style.display = text.includes(q) ? "" : "none";
    });
  });
})();


/* ── MOBILE NAV TOGGLE ───────────────────────────────────── */
function toggleNav() {
  document.getElementById("navLinks")?.classList.toggle("open");
}

/* ── PUSH NOTIFICATION MANAGER ──────────────────────────── */
const PushManager = {
  /** Register the service worker and return the SW registration. */
  async registerSW() {
    if (!("serviceWorker" in navigator)) return null;
    try {
      return await navigator.serviceWorker.register("/sw.js");
    } catch (e) {
      console.warn("SW registration failed:", e);
      return null;
    }
  },

  /** Request permission + subscribe to push. */
  async subscribe() {
    const reg = await this.registerSW();
    if (!reg) { alert("Push notifications not supported."); return false; }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      alert("Notification permission denied. Enable it in browser settings.");
      return false;
    }

    // Use a dummy VAPID-less subscription (works for local in-browser notifications)
    // For real web push, generate VAPID keys and pass applicationServerKey here.
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      // applicationServerKey: urlBase64ToUint8Array("YOUR_VAPID_PUBLIC_KEY")
    }).catch(() => null);

    if (!sub) {
      // Fallback: store a "soft" subscription flag for local notifications only
      await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "local", endpoint: "local" })
      });
      return true;
    }

    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub)
    });
    return true;
  },

  /** Unsubscribe. */
  async unsubscribe() {
    await fetch("/api/push/unsubscribe", { method: "POST" });
    const reg = await navigator.serviceWorker?.getRegistration();
    const sub = await reg?.pushManager?.getSubscription();
    await sub?.unsubscribe();
  },

  /** Check current status from server. */
  async status() {
    const res  = await fetch("/api/push/status");
    const data = await res.json();
    return data.subscribed;
  }
};


/**
 * Wire up a notification toggle button (id="notifToggle") if present.
 * Rendered in the timetable and dashboard pages.
 */
(async function initNotifToggle() {
  const btn = document.getElementById("notifToggle");
  if (!btn) return;

  // Reflect current state
  const active = await PushManager.status();
  btn.classList.toggle("active", active);
  btn.querySelector(".notif-label").textContent =
    active ? "Notifications On" : "Notifications Off";

  btn.addEventListener("click", async () => {
    const isActive = btn.classList.contains("active");
    if (isActive) {
      await PushManager.unsubscribe();
      btn.classList.remove("active");
      btn.querySelector(".notif-label").textContent = "Notifications Off";
    } else {
      const ok = await PushManager.subscribe();
      if (ok) {
        btn.classList.add("active");
        btn.querySelector(".notif-label").textContent = "Notifications On";
        // Schedule a test reminder 5 seconds later
        setTimeout(() => {
          if (Notification.permission === "granted") {
            new Notification("✅ StudyPlan", {
              body: "Notifications are now active! We'll remind you to study.",
              icon: "/static/img/icon-192.png"
            });
          }
        }, 5000);
      }
    }
  });
})();


/* ── STUDY REMINDER SCHEDULER (local, no server push needed) ── */
/**
 * Schedules local (in-page) notifications at study start times
 * based on today's timetable. Works entirely client-side.
 * Runs on the timetable page where window.todaySchedule is set.
 */
(function scheduleLocalReminders() {
  if (!window.todaySchedule || !Array.isArray(window.todaySchedule)) return;
  if (Notification.permission !== "granted") return;

  const now = new Date();
  window.todaySchedule.forEach(slot => {
    const [h, m] = slot.start.split(":").map(Number);
    const slotTime = new Date(now);
    slotTime.setHours(h, m, 0, 0);

    // Remind 5 minutes before
    const reminderTime = new Date(slotTime.getTime() - 5 * 60 * 1000);
    const msUntil = reminderTime - now;
    if (msUntil > 0 && msUntil < 24 * 60 * 60 * 1000) {
      setTimeout(() => {
        new Notification(`⏰ StudyPlan: ${slot.subject} starts soon`, {
          body: `Your ${slot.subject} session starts at ${slot.start}. Get ready!`,
          icon: "/static/img/icon-192.png",
          tag:  `slot-${slot.subject}-${slot.start}`
        });
      }, msUntil);
    }
  });
})();


/* ── NAVBAR NOTIFICATION BELL ────────────────────────────── */
async function navNotifToggle() {
  const btn  = document.getElementById("navNotifBtn");
  if (!btn) return;
  const active = btn.classList.contains("active");
  if (active) {
    await PushManager.unsubscribe();
    btn.classList.remove("active");
    document.getElementById("navBellIcon").className = "bi bi-bell";
  } else {
    const ok = await PushManager.subscribe();
    if (ok) {
      btn.classList.add("active");
      document.getElementById("navBellIcon").className = "bi bi-bell-fill";
    }
  }
}

// Init bell state on page load
(async function initNavBell() {
  const btn = document.getElementById("navNotifBtn");
  if (!btn) return;
  try {
    const active = await PushManager.status();
    btn.classList.toggle("active", active);
    document.getElementById("navBellIcon").className =
      active ? "bi bi-bell-fill" : "bi bi-bell";
  } catch(e) {}
})();
