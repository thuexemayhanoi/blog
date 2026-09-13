/**
 * NGUYỄN TÚ BLOG - PREMIUM ULTRA
 * Main JavaScript
 */

// Check if prefers reduced motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// Mobile menu state
let mobileMenuOpen = false;

// Close mobile menu when clicking outside
document.addEventListener('click', function(e) {
  const mobileMenu = document.querySelector('.mobile-menu');
  const mobileToggle = document.querySelector('.mobile-menu-toggle');
  
  if (mobileMenu && mobileToggle && mobileMenuOpen) {
    if (!mobileMenu.contains(e.target) && !mobileToggle.contains(e.target)) {
      closeMobileMenu();
    }
  }
});

// Close mobile menu when pressing Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && mobileMenuOpen) {
    closeMobileMenu();
  }
});

// Close mobile menu function
function closeMobileMenu() {
  const mobileMenu = document.querySelector('.mobile-menu');
  const mobileToggle = document.querySelector('.mobile-menu-toggle');
  
  if (mobileMenu && mobileToggle) {
    mobileMenu.classList.remove('active');
    mobileToggle.setAttribute('aria-expanded', 'false');
    mobileMenuOpen = false;
    document.body.classList.remove('mobile-menu-open');
  }
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
  const dropdowns = document.querySelectorAll('.dropdown');
  
  dropdowns.forEach(function(dropdown) {
    if (!dropdown.contains(e.target)) {
      const toggle = dropdown.querySelector('.dropdown-toggle');
      const menu = dropdown.querySelector('.dropdown-menu');
      
      if (toggle && menu) {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.remove('active');
      }
    }
  });
});

// Close dropdowns when pressing Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(function(dropdown) {
      const toggle = dropdown.querySelector('.dropdown-toggle');
      const menu = dropdown.querySelector('.dropdown-menu');
      
      if (toggle && menu) {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.remove('active');
      }
    });
  }
});

// Handle dropdown keyboard navigation
document.addEventListener('keydown', function(e) {
  const dropdowns = document.querySelectorAll('.dropdown');
  
  dropdowns.forEach(function(dropdown) {
    const toggle = dropdown.querySelector('.dropdown-toggle');
    const menu = dropdown.querySelector('.dropdown-menu');
    const items = menu ? menu.querySelectorAll('.dropdown-item') : [];
    
    if (toggle && menu && items.length > 0) {
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      
      if (isExpanded) {
        // Handle arrow keys in dropdown menu
        items.forEach(function(item, index) {
          if (item.getAttribute('tabindex') === '0') {
            if (e.key === 'ArrowDown' && index < items.length - 1) {
              e.preventDefault();
              items[index + 1].focus();
            } else if (e.key === 'ArrowUp' && index > 0) {
              e.preventDefault();
              items[index - 1].focus();
            } else if (e.key === 'Escape') {
              e.preventDefault();
              toggle.setAttribute('aria-expanded', 'false');
              menu.classList.remove('active');
              toggle.focus();
            }
          }
        });
      }
    }
  });
});

// Handle mobile submenu keyboard navigation
document.addEventListener('keydown', function(e) {
  const submenuToggles = document.querySelectorAll('.submenu-toggle');
  
  submenuToggles.forEach(function(toggle) {
    const submenuId = toggle.getAttribute('aria-controls');
    const submenu = submenuId ? document.getElementById(submenuId) : null;
    const links = submenu ? submenu.querySelectorAll('.mobile-submenu-link') : [];
    
    if (toggle && submenu && links.length > 0) {
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      
      if (isExpanded) {
        links.forEach(function(link, index) {
          if (link.getAttribute('tabindex') === '0') {
            if (e.key === 'ArrowDown' && index < links.length - 1) {
              e.preventDefault();
              links[index + 1].focus();
            } else if (e.key === 'ArrowUp' && index > 0) {
              e.preventDefault();
              links[index - 1].focus();
            } else if (e.key === 'Escape') {
              e.preventDefault();
              toggle.setAttribute('aria-expanded', 'false');
              submenu.classList.remove('active');
              toggle.focus();
            }
          }
        });
      }
    }
  });
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
  anchor.addEventListener('click', function(e) {
    const href = this.getAttribute('href');
    if (href !== '#') {
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        const headerOffset = 80;
        const elementPosition = target.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        
        if (!prefersReducedMotion.matches) {
          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
        } else {
          window.scrollTo(0, offsetPosition);
        }
        
        // Update URL without adding to history
        history.replaceState(null, null, href);
      }
    }
  });
});

// Add focus styles for keyboard navigation
document.addEventListener('DOMContentLoaded', function() {
  // Add tabindex to all interactive elements
  const interactiveElements = document.querySelectorAll('a[href], button, [tabindex]');
  interactiveElements.forEach(function(el) {
    if (!el.hasAttribute('tabindex')) {
      el.setAttribute('tabindex', '0');
    }
  });
});

// Lazy load images
if ('IntersectionObserver' in window) {
  const lazyImages = document.querySelectorAll('img[data-src]');
  
  const imageObserver = new IntersectionObserver(function(entries, observer) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        observer.unobserve(img);
      }
    });
  });
  
  lazyImages.forEach(function(img) {
    imageObserver.observe(img);
  });
}

// Console message
console.log('%c🚀 NGUYỄN TÚ BLOG', 'color: #007AFF; font-size: 24px; font-weight: bold;');
console.log('%cPremium Ultra Version', 'color: #888; font-size: 12px;');