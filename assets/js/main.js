// DIGITAL FLAGSHIP EXPERIENCE
// Main JavaScript for NGUYỄN TÚ DIGITAL FLAGSHIP WORLD-CLASS EXPERIENCE

(function() {
  'use strict';

  var ThemeManager = {
    STORAGE_KEY: 'nguyentu-theme',
    init: function() {
      this._applySavedTheme();
      this._bindToggle();
    },
    _applySavedTheme: function() {
      try {
        var savedTheme = localStorage.getItem(this.STORAGE_KEY);
        if (savedTheme === 'dark') {
          document.documentElement.setAttribute('data-theme', 'dark');
        } else {
          document.documentElement.removeAttribute('data-theme');
        }
      } catch (e) {
        document.documentElement.removeAttribute('data-theme');
      }
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
      try {
        var currentTheme = document.documentElement.getAttribute('data-theme');
        var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        if (newTheme === 'dark') {
          document.documentElement.setAttribute('data-theme', 'dark');
        } else {
          document.documentElement.removeAttribute('data-theme');
        }
        localStorage.setItem(this.STORAGE_KEY, newTheme);
      } catch (e) {
        console.warn('ThemeManager: Could not save theme', e);
      }
    }
  };

  var MobileMenu = {
    init: function() {
      this._bindOpen();
      this._bindClose();
      this._bindEscape();
      this._bindLinks();
      this._bindScrollLock();
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
    _bindEscape: function() {
      var self = this;
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && document.body.classList.contains('mobile-menu-open')) {
          self.close();
        }
      });
    },
    _bindLinks: function() {
      var menuLinks = document.querySelectorAll('.mobile-submenu a, .mobile-menu__nav-link');
      var self = this;
      menuLinks.forEach(function(link) {
        link.addEventListener('click', function() {
          self.close();
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
      this._hideContactUI();
    },
    close: function() {
      document.body.classList.remove('mobile-menu-open');
      this._showContactUI();
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

  var Assistant = {
    init: function() {
      this._bindOpen();
      this._bindClose();
      this._bindEscape();
      this._bindScrollLock();
    },
    _bindOpen: function() {
      var openButtons = document.querySelectorAll('[data-assistant-open]');
      var self = this;
      openButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.open();
        });
      });
    },
    _bindClose: function() {
      var closeButtons = document.querySelectorAll('[data-assistant-close]');
      var self = this;
      closeButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.close();
        });
      });
    },
    _bindEscape: function() {
      var self = this;
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && document.body.classList.contains('assistant-open')) {
          self.close();
        }
      });
    },
    _bindScrollLock: function() {
      var self = this;
      var observer = new MutationObserver(function(mutations) {
        if (document.body.classList.contains('assistant-open')) {
          document.body.style.overflow = 'hidden';
        } else {
          document.body.style.overflow = '';
        }
      });
      observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    },
    open: function() {
      document.body.classList.add('assistant-open');
      MobileMenu._hideContactUI();
    },
    close: function() {
      document.body.classList.remove('assistant-open');
      MobileMenu._showContactUI();
    }
  };

  var Dropdown = {
    init: function() {
      this._bindHover();
    },
    _bindHover: function() {
      var navItems = document.querySelectorAll('.header__nav-item');
      navItems.forEach(function(item) {
        var dropdown = item.querySelector('.header__dropdown');
        if (dropdown) {
          item.addEventListener('mouseenter', function() {
            dropdown.style.opacity = '1';
            dropdown.style.visibility = 'visible';
            dropdown.style.transform = 'translateY(0)';
          });
          item.addEventListener('mouseleave', function() {
            dropdown.style.opacity = '';
            dropdown.style.visibility = '';
            dropdown.style.transform = '';
          });
        }
      });
    }
  };

  function init() {
    ThemeManager.init();
    MobileMenu.init();
    Assistant.init();
    Dropdown.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();