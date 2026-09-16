/**
 * DIGITAL FLAGSHIP EXPERIENCE
 * FIXED: Removed duplicate Assistant controller - assistant.js is sole chatbot handler
 * Main JavaScript for NGUYEN TU DIGITAL FLAGSHIP WORLD-CLASS EXPERIENCE
 */

(function() {
  'use strict';

  var ThemeManager = {
    STORAGE_KEY: 'nguyentu-theme',
    init: function() {
      this._applySavedTheme();
      this._bindToggle();
    },
    _applySavedTheme: function() {
      var theme = 'light';
      try {
        var savedTheme = localStorage.getItem(this.STORAGE_KEY);
        if (savedTheme === 'dark' || savedTheme === 'light') {
          theme = savedTheme;
        } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
          theme = 'dark';
        }
      } catch (e) {
        theme = 'light';
      }
      document.documentElement.setAttribute('data-theme', theme);
      this._updateThemeIcons();
    },
    _bindToggle: function() {
      var toggleButtons = document.querySelectorAll('[data-theme-toggle]');
      var self = this;
      toggleButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.toggle();
        });
      });
    },
    toggle: function() {
      var currentTheme = document.documentElement.getAttribute('data-theme');
      var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      try {
        localStorage.setItem(this.STORAGE_KEY, newTheme);
      } catch (e) {
        console.warn('ThemeManager: Could not save theme', e);
      }
      this._updateThemeIcons();
    },
    _updateThemeIcons: function() {
      var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      var sunIcons = document.querySelectorAll('.theme-icon-sun');
      var moonIcons = document.querySelectorAll('.theme-icon-moon');
      var toggleButtons = document.querySelectorAll('[data-theme-toggle]')

;
      
      sunIcons.forEach(function(icon) { icon.style.display = isDark ? 'none' : 'block'; });
      moonIcons.forEach(function(icon) { icon.style.display = isDark ? 'block' : 'none'; });
      
      toggleButtons.forEach(function(btn) {
        if (isDark) {
          btn.setAttribute('aria-label', 'Chuyển sang giao diện sáng');
        } else {
          btn.setAttribute('aria-label', 'Chuyển sang giao diện tối');
        }
      });
    }
  };

  var MobileMenu = {
    init: function() {
      this._bindOpen();
      this._bindClose();
      this._bindOverlay();
      this._bindEscape();
      this._bindLinks();
      this._bindScrollLock();
      this._bindSubmenuToggles();
    },
    _bindOpen: function() {
      var openButtons = document.querySelectorAll('[data-mobile-menu-open]');
      var self = this;
      openButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.open();
        });
      });
    },
    _bindClose: function() {
      var closeButtons = document.querySelectorAll('[data-mobile-menu-close]');
      var self = this;
      closeButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.close();
        });
      });
    },
    _bindOverlay: function() {
      var self = this;
      var overlay = document.querySelector('.mobile-menu');
      if (!overlay) return;
      overlay.addEventListener('click', function(e) {
        if (!e.target.closest('.mobile-menu-inner')) {
          self.close();
        }
      });
    },
    _bindEscape: function() {
      var self = this;
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && document.body.classList.contains('mobile-menu-open')) {
          self.close();
        }
      });
    },
    _bindLinks: function() {
      var menuLinks = document.querySelectorAll('.mobile-submenu a, .mobile-nav-link');
      var self = this;
      menuLinks.forEach(function(link) {
        link.addEventListener('click', function() {
          self.close();
        });
      });
    },
    _bindSubmenuToggles: function() {
      var submenuToggles = document.querySelectorAll('.submenu-toggle');
      var self = this;
      submenuToggles.forEach(function(toggle)
 
{
        toggle.addEventListener('click', function(e) {
          e.preventDefault();
          var expanded = this.getAttribute('aria-expanded') === 'true';
          this.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        });
      });
    },
    _bindScrollLock: function() {
      var self = this;
      var observer = new MutationObserver(function(mutations) {
        if (document.body.classList.contains('mobile-menu-open')) {
          document.body.style.overflow = 'hidden';
        } else {
          document.body.style.overflow = '';
        }
      });
      observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    },
    open: function() {
      document.body.classList.add('mobile-menu-open');
      this._setToggleState(true);
      this._hideContactUI();
    },
    close: function() {
      document.body.classList.remove('mobile-menu-open');
      this._setToggleState(false);
      this._resetSubmenus();
      this._showContactUI();
    },
    _setToggleState: function(expanded) {
      var openButtons = document.querySelectorAll('[data-mobile-menu-open]');
      openButtons.forEach(function(btn) {
        btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        btn.setAttribute('aria-label', expanded ? 'Đóng menu' : 'Mở menu');
      });
    },
    _resetSubmenus: function() {
      var submenuToggles = document.querySelectorAll('.submenu-toggle');
      submenuToggles.forEach(function(toggle) {
        toggle.setAttribute('aria-expanded', 'false');
      });
    },
    _hideContactUI: function() {
      var mobileContactBar = document.querySelector('.mobile-contact-bar');
      var contactRail = document.querySelector('.contact-rail');
      if (mobileContactBar) mobileContactBar.style.display = 'none';
      if (contactRail) contactRail.style.display = 'none';
    },
    _showContactUI: function() {
      var mobileContactBar = document.querySelector('.mobile-contact-bar');
      var contactRail = document.querySelector('.contact-rail');
      if (mobileContactBar) mobileContactBar.style.display = '';
      if (contactRail) contactRail.style.display = '';
    }
  };

  var Dropdown = {
    init: function() {
      this._bindHover();
    },
    _bindHover: function() {
      var dropdowns = document.querySelectorAll('.dropdown');
      
      dropdowns.forEach(function(dropdownItem) {
        var dropdownToggle = dropdownItem.querySelector('.dropdown-toggle');
        var dropdownMenu = dropdownItem.querySelector('.dropdown-menu');
        if (dropdownToggle && dropdownMenu) {
          dropdownItem.addEventListener('mouseenter', function() {
            dropdownMenu.style.opacity = '1';
            dropdownMenu.style.visibility = 'visible';
            dropdownMenu.style.transform = 'translateY(0)';
          });
          dropdownItem.addEventListener('mouseleave', function() {
            dropdownMenu.style.opacity = '';
            dropdownMenu.style.visibility = '';
            dropdownMenu.style.transform = '';
          });
        }
      });
    }
  };

  var FooterAccordion = {
    init: function() {
      this._sections = Array.prototype.slice.call(document.querySelectorAll('.footer-section'));
      if (!this._sections.length) return;
      this._mq = window.matchMedia('(min-width: 768px)');
      var self = this;
      var onChange = function() { self._sync(); };
      if (typeof this._mq.addEventListener === 'function') {
        this._mq.addEventListener('change', onChange);
      } else if (typeof this._mq.addListener === 'function') {
        this._mq.addListener(onChange);
      }
      this._sections.forEach(function(section) {
        var summary = section.querySelector('.footer-section-summary');
        if (summary) {
          summary.addEventListener('click', function(e) {
            if (self._mq.matches) {
              e.preventDefault();
            }
          });
        }
      });
      this._sync();
    },
    _sync: function() {
      var open = this._mq.matches;
      this._sections.forEach(function(section) {
        section.open = open;
      });
    }
  };

  function init() {
    ThemeManager.init();
    MobileMenu.init();
    Dropdown.init();
    FooterAccordion.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();