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

  var BusinessStatus = {
    OPEN_HOUR: 9,
    CLOSE_HOUR: 21,
    TIME_ZONE: 'Asia/Ho_Chi_Minh',
    init: function() {
      this._update();
      var self = this;
      window.setInterval(function() { self._update(); }, 60000);
    },
    _hanoiHour: function() {
      try {
        var formatter = new Intl.DateTimeFormat('en-US', {
          timeZone: this.TIME_ZONE,
          hour: 'numeric',
          hour12: false
        });
        var hour = parseInt(formatter.format(new Date()), 10);
        return isNaN(hour) ? -1 : hour;
      } catch (e) {
        return -1;
      }
    },
    _isOpen: function() {
      var hour = this._hanoiHour();
      return hour >= this.OPEN_HOUR && hour < this.CLOSE_HOUR;
    },
    _update: function() {
      var open = this._isOpen();
      var badges = document.querySelectorAll('[data-business-status]');
      badges.forEach(function(badge) {
        badge.classList.toggle('is-open', open);
        badge.classList.toggle('is-closed', !open);
        var text = badge.querySelector('.business-status-text');
        if (!text) return;
        var full = badge.hasAttribute('data-status-full');
        text.textContent = open
          ? (full ? 'Đang mở cửa' : 'Đang mở')
          : (full ? 'Đã đóng cửa · Mở cửa lúc 09:00' : 'Đã đóng');
      });
    }
  };

  var MobileMenu = {
    init: function() {
      this.panel = document.getElementById('mobileMenu');
      if (!this.panel) return;
      this.panel.inert = true;
      this.panel.setAttribute('aria-hidden', 'true');
      this._bindOpen();
      this._bindClose();
      this._bindOverlay();
      this._bindKeys();
      this._bindLinks();
      this._bindSubmenuToggles();
      this._bindViewport();
    },
    _bindOpen: function() {
      var self = this;
      document.querySelectorAll('[data-mobile-menu-open]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.open(btn);
        });
      });
    },
    _bindClose: function() {
      var self = this;
      document.querySelectorAll('[data-mobile-menu-close]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          self.close();
        });
      });
    },
    _bindOverlay: function() {
      var self = this;
      this.panel.addEventListener('click', function(e) {
        if (!e.target.closest('.mobile-menu-inner')) self.close();
      });
    },
    _bindKeys: function() {
      var self = this;
      document.addEventListener('keydown', function(e) {
        if (!document.body.classList.contains('mobile-menu-open')) return;
        if (e.key === 'Escape') {
          e.preventDefault();
          self.close();
          return;
        }
        if (e.key !== 'Tab') return;
        var focusable = Array.prototype.slice.call(self.panel.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )).filter(function(el) {
          return !el.closest('[inert], [aria-hidden="true"]') &&
            el.getClientRects().length > 0;
        });
        if (!focusable.length) {
          e.preventDefault();
          return;
        }
        var first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && (document.activeElement === first ||
            !self.panel.contains(document.activeElement))) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (document.activeElement === last ||
            !self.panel.contains(document.activeElement))) {
          e.preventDefault();
          first.focus();
        }
      });
    },
    _bindLinks: function() {
      var self = this;
      this.panel.querySelectorAll('.mobile-submenu a, .mobile-nav-link').forEach(function(link) {
        link.addEventListener('click', function() { self.close(); });
      });
    },
    _bindSubmenuToggles: function() {
      var self = this;
      this.panel.querySelectorAll('.submenu-toggle').forEach(function(toggle) {
        toggle.addEventListener('click', function(e) {
          e.preventDefault();
          var open = this.getAttribute('aria-expanded') !== 'true';
          self._setSubmenu(this, open);
        });
      });
    },
    _setSubmenu: function(toggle, open) {
      var id = toggle.getAttribute('aria-controls');
      var submenu = id && document.getElementById(id);
      if (!submenu) return;
      if (!open && submenu.contains(document.activeElement)) toggle.focus();
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      submenu.setAttribute('aria-hidden', open ? 'false' : 'true');
      submenu.inert = !open;
    },
    _bindViewport: function() {
      var self = this;
      window.addEventListener('resize', function() {
        if (window.innerWidth >= 1200 &&
            document.body.classList.contains('mobile-menu-open')) self.close();
      });
    },
    open: function(opener) {
      if (!this.panel || document.body.classList.contains('mobile-menu-open')) return;
      this._opener = opener || document.activeElement;
      this.panel.inert = false;
      this.panel.setAttribute('aria-hidden', 'false');
      document.body.classList.add('mobile-menu-open');
      document.body.style.overflow = 'hidden';
      this._setToggleState(true);
      this._hideContactUI();
      var closeButton = this.panel.querySelector('[data-mobile-menu-close]');
      if (closeButton) closeButton.focus();
    },
    close: function() {
      if (!this.panel || !document.body.classList.contains('mobile-menu-open')) return;
      document.body.classList.remove('mobile-menu-open');
      document.body.style.overflow = '';
      this._setToggleState(false);
      this._resetSubmenus();
      this._showContactUI();
      this.panel.setAttribute('aria-hidden', 'true');
      this.panel.inert = true;
      if (this._opener && document.contains(this._opener) &&
          this._opener.getClientRects().length > 0) this._opener.focus();
      this._opener = null;
    },
    _setToggleState: function(expanded) {
      document.querySelectorAll('[data-mobile-menu-open]').forEach(function(btn) {
        btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        btn.setAttribute('aria-label', expanded ? 'Đóng menu' : 'Mở menu');
      });
    },
    _resetSubmenus: function() {
      var self = this;
      this.panel.querySelectorAll('.submenu-toggle').forEach(function(toggle) {
        self._setSubmenu(toggle, false);
      });
    },
    _hideContactUI: function() {
      document.querySelectorAll('.mobile-contact-bar, .contact-rail').forEach(function(el) {
        el.style.display = 'none';
      });
    },
    _showContactUI: function() {
      document.querySelectorAll('.mobile-contact-bar, .contact-rail').forEach(function(el) {
        el.style.display = '';
      });
    }
  };

  var Dropdown = {
    init: function() {
      var items = Array.prototype.slice.call(document.querySelectorAll('.desktop-nav .dropdown'));
      function setOpen(item, open) {
        var toggle = item.querySelector('.dropdown-toggle');
        var menu = item.querySelector('.dropdown-menu');
        if (!toggle || !menu) return;
        item.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        menu.setAttribute('aria-hidden', open ? 'false' : 'true');
      }
      function closeOthers(keep) {
        items.forEach(function(item) { if (item !== keep) setOpen(item, false); });
      }
      items.forEach(function(item) {
        var toggle = item.querySelector('.dropdown-toggle');
        var menu = item.querySelector('.dropdown-menu');
        if (!toggle || !menu) return;
        menu.setAttribute('aria-hidden', 'true');
        toggle.addEventListener('click', function(e) {
          e.preventDefault();
          var open = toggle.getAttribute('aria-expanded') !== 'true';
          closeOthers(item);
          setOpen(item, open);
        });
        toggle.addEventListener('keydown', function(e) {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            closeOthers(item);
            setOpen(item, true);
            var first = menu.querySelector('a[href]');
            if (first) first.focus();
          }
        });
        item.addEventListener('mouseenter', function() {
          closeOthers(item);
          setOpen(item, true);
        });
        item.addEventListener('mouseleave', function() {
          if (!item.contains(document.activeElement)) setOpen(item, false);
        });
        item.addEventListener('focusin', function(e) {
          if (e.target !== toggle) {
            closeOthers(item);
            setOpen(item, true);
          }
        });
        item.addEventListener('focusout', function() {
          window.setTimeout(function() {
            if (!item.contains(document.activeElement)) setOpen(item, false);
          }, 0);
        });
        item.addEventListener('keydown', function(e) {
          if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
            e.preventDefault();
            setOpen(item, false);
            toggle.focus();
          }
        });
      });
      document.addEventListener('pointerdown', function(e) {
        if (!e.target.closest('.desktop-nav .dropdown')) closeOthers(null);
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
    BusinessStatus.init();
    Dropdown.init();
    FooterAccordion.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();