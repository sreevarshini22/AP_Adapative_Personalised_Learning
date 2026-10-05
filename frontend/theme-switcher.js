/**
 * Universal Dark / Light Mode Switcher
 * AP Adaptive Education Platform
 * Persists user choice in localStorage with instant DOM attribute toggling.
 */

(function () {
  const THEME_KEY = 'ap_adaptive_theme';

  function getPreferredTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
    // Default to dark theme for academic & quantum visual aesthetics, or check system
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    updateThemeToggleUI(theme);
  }

  function updateThemeToggleUI(theme) {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      const icon = btn.querySelector('i');
      const text = btn.querySelector('.theme-text');
      if (theme === 'light') {
        if (icon) icon.className = 'fa-solid fa-moon';
        if (text) text.textContent = 'Dark Mode';
        btn.setAttribute('title', 'Switch to Dark Mode');
        btn.setAttribute('aria-label', 'Switch to Dark Mode');
      } else {
        if (icon) icon.className = 'fa-solid fa-sun';
        if (text) text.textContent = 'Light Mode';
        btn.setAttribute('title', 'Switch to Light Mode');
        btn.setAttribute('aria-label', 'Switch to Light Mode');
      }
    });
  }

  window.toggleTheme = function () {
    const current = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
    const next = current === 'light' ? 'dark' : 'light';
    applyTheme(next);
  };

  // Immediate initial theme application to avoid flash
  const initialTheme = getPreferredTheme();
  document.documentElement.setAttribute('data-theme', initialTheme);

  // Bind on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    updateThemeToggleUI(initialTheme);
  });
})();
