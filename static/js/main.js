/* FitBuddy AI — Main JavaScript */

"use strict";

// ── Clipboard utility ────────────────────────────────────────────────────────
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText;
  navigator.clipboard.writeText(text).then(() => {
    // Brief visual feedback
    const btns = document.querySelectorAll('[onclick*="copyToClipboard"]');
    btns.forEach(btn => {
      const orig = btn.innerHTML;
      btn.innerHTML = '<i class="bi bi-clipboard-check me-1"></i>Copied!';
      btn.classList.add("btn-success");
      btn.classList.remove("btn-outline-secondary");
      setTimeout(() => {
        btn.innerHTML = orig;
        btn.classList.remove("btn-success");
        btn.classList.add("btn-outline-secondary");
      }, 2000);
    });
  }).catch(() => {
    // Fallback for older browsers
    const range = document.createRange();
    range.selectNode(el);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand("copy");
    window.getSelection().removeAllRanges();
  });
}

// ── Motivation refresh on home page ─────────────────────────────────────────
function refreshMotivation() {
  const card = document.getElementById("motivationText");
  if (!card) return;
  const spinner = document.getElementById("motivationSpinner");
  if (spinner) spinner.classList.remove("d-none");
  card.style.opacity = "0.4";

  fetch("/api/motivation")
    .then(r => r.json())
    .then(data => {
      card.textContent = data.quote || card.textContent;
      card.style.opacity = "1";
      if (spinner) spinner.classList.add("d-none");
    })
    .catch(() => {
      card.style.opacity = "1";
      if (spinner) spinner.classList.add("d-none");
    });
}

// ── Quick workout widget ─────────────────────────────────────────────────────
function loadQuickWorkout() {
  const container = document.getElementById("quickWorkoutResult");
  const btn = document.getElementById("quickWorkoutBtn");
  if (!container || !btn) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading…';

  fetch("/api/quick-workout")
    .then(r => r.json())
    .then(data => {
      container.textContent = data.workout || "Could not load workout.";
      container.style.display = "block";
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
    })
    .catch(() => {
      container.textContent = "Could not load workout. Please try again.";
      container.style.display = "block";
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
    });
}

// ── Form loading states ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Disable submit buttons on form submission
  document.querySelectorAll("form:not([data-no-loading])").forEach(form => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector('[type="submit"]');
      if (btn && !btn.id) {   // Only if not already handled by page-specific script
        btn.disabled = true;
        const orig = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Please wait…';
        // Re-enable after 30s as a safety net
        setTimeout(() => { btn.disabled = false; btn.innerHTML = orig; }, 30000);
      }
    });
  });

  // Animate stat values on scroll
  const statValues = document.querySelectorAll(".stat-value");
  if ("IntersectionObserver" in window) {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.style.transform = "translateY(0)";
          entry.target.style.opacity  = "1";
        }
      });
    }, { threshold: 0.3 });
    statValues.forEach(el => {
      el.style.transform = "translateY(12px)";
      el.style.opacity   = "0";
      el.style.transition = "transform .4s ease, opacity .4s ease";
      obs.observe(el);
    });
  }

  // Bootstrap tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el, { trigger: "hover" });
  });

  // Auto-dismiss alerts after 5 seconds
  document.querySelectorAll(".alert.alert-success").forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });

  // BMI marker animation — re-trigger on load
  const bmiMarker = document.querySelector(".bmi-marker");
  if (bmiMarker) {
    const targetLeft = bmiMarker.style.left;
    bmiMarker.style.left = "0%";
    setTimeout(() => { bmiMarker.style.left = targetLeft; }, 100);
  }

  // Water glass progressive fill animation
  const glasses = document.querySelectorAll(".water-glass");
  glasses.forEach((g, i) => {
    g.style.opacity = "0";
    g.style.transform = "scale(0.5)";
    g.style.transition = `opacity .3s ease ${i * 50}ms, transform .3s ease ${i * 50}ms`;
    setTimeout(() => {
      g.style.opacity = "1";
      g.style.transform = "scale(1)";
    }, 200 + i * 50);
  });
});
