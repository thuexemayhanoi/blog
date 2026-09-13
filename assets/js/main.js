/**
 * NGUYEN TU BLOG - PREMIUM ULTRA
 * Main JavaScript - Theme, Mobile Menu, Navigation
 */

// ============================================
// THEME MANAGEMENT
// ============================================

const ThemeManager = {
  STORAGE_KEY: 'nguyentu-theme',
  
  init() {
    // Check for saved theme
    const savedTheme = localStorage.getItem(this.STORAGE_KEY);
    if (savedTheme) {
      this.setTheme(savedTheme);
    } else {
      // Check system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      this.setTheme(prefersDark ? 'dark' : 'light');
    }
    
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem(this.STORAGE_KEY)) {
        this.setTheme(e.matches ? 'dark' : 'light');
      }
    });
    
    // Set up toggle buttons
    this.setupToggles();
  },
  
  setTheme(theme) {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    
    if (currentTheme !== theme) {
      html.setAttribute('data-theme', theme);
      localStorage.setItem(this.STORAGE_KEY, theme);
      this.updateToggleButtons();
    }
  },
  
  toggle() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    this.setTheme(newTheme);
  },
  
  getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
  },
  
  setupToggles() {
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      btn.addEventListener('click', () => this.toggle());
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.toggle();
        }
      });
    });
    
    this.updateToggleButtons();
  },
  
  updateToggleButtons() {
    const theme = this.getTheme();
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      const sun = btn.querySelector('.sun');
      const moon = btn.querySelector('.moon');
      
      if (sun && moon) {
        if (theme === 'dark') {
          sun.style.display = 'none';
          moon.style.display = 'inline';
        } else {
          sun.style.display = 'inline';
          moon.style.display = 'none';
        }
      }
      
      // Update aria-label
      btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    });
  }
};

// ============================================
// MOBILE MENU MANAGEMENT
// ============================================

const MobileMenu = {
  menu: null,
  toggle: null,
  closeBtn: null,
  isOpen: false,
  
  init() {
    this.menu = document.querySelector('.mobile-menu');
    this.toggle = document.querySelector('.mobile-menu-toggle');
    this.closeBtn = document.querySelector('.mobile-close');
    
    if (!this.menu || !this.toggle) return;
    
    // Set up event listeners
    this.toggle.addEventListener('click', () => this.toggleMenu());
    
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.close());
    }
    
    // Close on backdrop click
    this.menu.addEventListener('click', (e) => {
      if (e.target === this.menu) {
        this.close();
      }
    });
    
    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
    
    // Close when clicking a link
    this.menu.querySelectorAll('a[href]').forEach(link => {
      link.addEventListener('click', () => {
        // Small delay to allow navigation
        setTimeout(() => this.close(), 150);
      });
    });
    
    // Submenu toggles
    this.setupSubmenus();
  },
  
  toggleMenu() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  },
  
  open() {
    if (!this.menu || !this.toggle) return;
    
    this.menu.classList.add('active');
    this.toggle.setAttribute('aria-expanded', 'true');
    this.isOpen = true;
    document.body.classList.add('mobile-menu-open');
    
    // Focus first element
    const firstFocusable = this.menu.querySelector('a[href], button, [tabindex]:not([tabindex="-1"])');
    if (firstFocusable) {
      setTimeout(() => firstFocusable.focus(), 100);
    }
    
    // Hide quick contact bar
    const quickBar = document.querySelector('.quick-contact-mobile');
    if (quickBar) {
      quickBar.style.display = 'none';
    }
  },
  
  close() {
    if (!this.menu || !this.toggle) return;
    
    this.menu.classList.remove('active');
    this.toggle.setAttribute('aria-expanded', 'false');
    this.isOpen = false;
    document.body.classList.remove('mobile-menu-open');
    
    // Return focus
    this.toggle.focus();
    
    // Show quick contact bar
    const quickBar = document.querySelector('.quick-contact-mobile');
    if (quickBar) {
      quickBar.style.display = '';
    }
    
    // Close all submenus
    this.closeAllSubmenus();
  },
  
  setupSubmenus() {
    this.menu.querySelectorAll('.has-submenu > .submenu-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const submenu = btn.nextElementSibling;
        const isExpanded = btn.getAttribute('aria-expanded') === 'true';
        
        if (submenu) {
          if (isExpanded) {
            this.closeSubmenu(btn, submenu);
          } else {
            this.openSubmenu(btn, submenu);
          }
        }
      });
    });
  },
  
  openSubmenu(btn, submenu) {
    btn.setAttribute('aria-expanded', 'true');
    submenu.classList.add('active');
    submenu.style.maxHeight = submenu.scrollHeight + 'px';
  },
  
  closeSubmenu(btn, submenu) {
    btn.setAttribute('aria-expanded', 'false');
    submenu.classList.remove('active');
    submenu.style.maxHeight = null;
  },
  
  closeAllSubmenus() {
    this.menu.querySelectorAll('.submenu-toggle').forEach(btn => {
      const submenu = btn.nextElementSibling;
      if (submenu) {
        btn.setAttribute('aria-expanded', 'false');
        submenu.classList.remove('active');
        submenu.style.maxHeight = null;
      }
    });
  }
};

// ============================================
// DESKTOP DROPDOWN MENU
// ============================================

const DropdownMenu = {
  init() {
    document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const menu = toggle.nextElementSibling;
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        
        if (menu) {
          if (isExpanded) {
            this.closeDropdown(toggle, menu);
          } else {
            // Close other dropdowns
            document.querySelectorAll('.dropdown-toggle').forEach(otherToggle => {
              if (otherToggle !== toggle) {
                const otherMenu = otherToggle.nextElementSibling;
                if (otherMenu) {
                  this.closeDropdown(otherToggle, otherMenu);
                }
              }
            });
            this.openDropdown(toggle, menu);
          }
        }
      });
      
      // Keyboard support
      toggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle.click();
        }
      });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
          const menu = toggle.nextElementSibling;
          if (menu) {
            this.closeDropdown(toggle, menu);
          }
        });
      }
    });
    
    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
          const menu = toggle.nextElementSibling;
          if (menu && menu.classList.contains('active')) {
            this.closeDropdown(toggle, menu);
            toggle.focus();
          }
        });
      }
    });
  },
  
  openDropdown(toggle, menu) {
    toggle.setAttribute('aria-expanded', 'true');
    menu.classList.add('active');
  },
  
  closeDropdown(toggle, menu) {
    toggle.setAttribute('aria-expanded', 'false');
    menu.classList.remove('active');
  }
};

// ============================================
// QUICK CONTACT BAR
// ============================================

const QuickContact = {
  init() {
    const desktopBar = document.querySelector('.quick-contact-desktop');
    const mobileBar = document.querySelector('.quick-contact-mobile');
    
    // Hide mobile bar when menu or assistant opens
    const observer = new MutationObserver((mutations) => {
      const menuOpen = document.body.classList.contains('mobile-menu-open');
      const assistantOpen = document.body.classList.contains('assistant-open');
      
      if (mobileBar) {
        if (menuOpen || assistantOpen) {
          mobileBar.style.display = 'none';
        } else {
          mobileBar.style.display = '';
        }
      }
    });
    
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class']
    });
  }
};

// ============================================
// SMOOTH SCROLL
// ============================================

const SmoothScroll = {
  init() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', (e) => {
        const href = anchor.getAttribute('href');
        if (href === '#') return;
        
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          const headerOffset = 80;
          const elementPosition = target.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
          
          const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
          
          if (!prefersReducedMotion) {
            window.scrollTo({
              top: offsetPosition,
              behavior: 'smooth'
            });
          } else {
            window.scrollTo(0, offsetPosition);
          }
          
          history.replaceState(null, null, href);
        }
      });
    });
  }
};

// ============================================
// LAZY LOAD IMAGES
// ============================================

const LazyLoad = {
  init() {
    if ('IntersectionObserver' in window) {
      const lazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]');
      
      const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
            }
            img.loading = 'eager';
            observer.unobserve(img);
          }
        });
      });
      
      lazyImages.forEach(img => {
        imageObserver.observe(img);
      });
    }
  }
};

// ============================================
// ACCESSIBILITY ENHANCEMENTS
// ============================================

const Accessibility = {
  init() {
    // Add focus styles for keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        document.body.classList.add('keyboard-nav');
      }
    });
    
    document.addEventListener('mousedown', () => {
      document.body.classList.remove('keyboard-nav');
    });
    
    // Ensure all interactive elements have tabindex
    document.querySelectorAll('a[href], button, [role="button"], [role="link"]').forEach(el => {
      if (!el.hasAttribute('tabindex')) {
        el.setAttribute('tabindex', '0');
      }
    });
  }
};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
  // Initialize all modules
  ThemeManager.init();
  MobileMenu.init();
  DropdownMenu.init();
  QuickContact.init();
  SmoothScroll.init();
  LazyLoad.init();
  Accessibility.init();
  
  // Console message
  console.log('%c NGUYEN TU BLOG', 'color: #007AFF; font-size: 24px; font-weight: bold;');
  console.log('%c Premium Ultra Version', 'color: #888; font-size: 12px;');
});

// Export for use in other modules
window.NguyenTuTheme = ThemeManager;
window.NguyenTuMobileMenu = MobileMenu;
