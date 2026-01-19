// Theme management for AbaQuiz Admin
// Handles system preference detection and manual toggle with localStorage persistence

document.addEventListener('alpine:init', () => {
  Alpine.data('themeManager', () => ({
    isDark: false,

    init() {
      // Check localStorage first, then system preference
      const stored = localStorage.getItem('theme');
      if (stored) {
        this.isDark = stored === 'dark';
      } else {
        this.isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      }
      this.applyTheme();

      // Listen for system preference changes (only applies if no manual override)
      window.matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', (e) => {
          if (!localStorage.getItem('theme')) {
            this.isDark = e.matches;
            this.applyTheme();
          }
        });
    },

    toggleTheme() {
      this.isDark = !this.isDark;
      localStorage.setItem('theme', this.isDark ? 'dark' : 'light');
      this.applyTheme();
    },

    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.isDark ? 'dark' : 'light');
    }
  }));

  // Sidebar state management
  Alpine.data('sidebarManager', () => ({
    collapsed: false,
    mobileOpen: false,

    init() {
      // Check localStorage for collapsed preference
      const stored = localStorage.getItem('sidebar-collapsed');
      if (stored !== null) {
        this.collapsed = stored === 'true';
      }

      // Auto-collapse on smaller screens
      this.handleResize();
      window.addEventListener('resize', () => this.handleResize());
    },

    handleResize() {
      // Auto-collapse below 1024px, auto-expand above
      if (window.innerWidth < 1024 && window.innerWidth >= 768) {
        this.collapsed = true;
      } else if (window.innerWidth >= 1024) {
        const stored = localStorage.getItem('sidebar-collapsed');
        this.collapsed = stored === 'true';
      }
      // Close mobile menu on resize to desktop
      if (window.innerWidth >= 768) {
        this.mobileOpen = false;
      }
    },

    toggleCollapse() {
      this.collapsed = !this.collapsed;
      localStorage.setItem('sidebar-collapsed', this.collapsed);
    },

    toggleMobile() {
      this.mobileOpen = !this.mobileOpen;
    },

    closeMobile() {
      this.mobileOpen = false;
    }
  }));
});

// Prevent FOUC (flash of unstyled content) by setting theme before render
(function() {
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = stored ? stored === 'dark' : prefersDark;
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
})();
