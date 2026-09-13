/**
 * NGUYỄN TÚ BLOG - PREMIUM ULTRA
 * Main JavaScript
 * Consolidated menu, dropdown, and UI interactions
 */

// ============================================
// CONFIGURATION
// ============================================
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// ============================================
// MOBILE MENU
// ============================================
let mobileMenuOpen = false;
const mobileMenu = document.querySelector('.mobile-menu');
const mobileToggle = document.querySelector('.mobile-menu-toggle');
const mobileClose = document.querySelector('.mobile-menu-close');
const body = document.body;

// Open mobile menu
function openMobileMenu() {
  if (mobileMenu && mobileToggle) {
    mobileMenu.classList.add('active');
    mobileToggle.classList.add('active');
    mobileToggle.setAttribute('aria-expanded', 'true');
    mobileMenuOpen = true;
    body.classList.add('mobile-menu-open');
    body.style.overflow = 'hidden';
  }
}

// Close mobile menu
function closeMobileMenu() {
  if (mobileMenu && mobileToggle) {
    mobileMenu.classList.remove('active');
    mobileToggle.classList.remove('active');
    mobileToggle.setAttribute('aria-expanded', 'false');
    mobileMenuOpen = false;
    body.classList.remove('mobile-menu-open');
    body.style.overflow = '';
    
    // Close all submenus
    closeAllSubmenus();
  }
}

// Toggle mobile menu
function toggleMobileMenu() {
  if (mobileMenuOpen) {
    closeMobileMenu();
  } else {
    openMobileMenu();
  }
}

// Close all mobile submenus
function closeAllSubmenus() {
  const submenuToggles = document.querySelectorAll('.submenu-toggle');
  submenuToggles.forEach(toggle => {
    toggle.setAttribute('aria-expanded', 'false');
    const submenuId = toggle.getAttribute('aria-controls');
    const submenu = submenuId ? document.getElementById(submenuId) : null;
    if (submenu) {
      submenu.classList.remove('active');
    }
  });
}

// Handle mobile menu toggle click
if (mobileToggle) {
  mobileToggle.addEventListener('click', function(e) {
    e.stopPropagation();
    toggleMobileMenu();
  });
}

// Handle mobile menu close click
if (mobileClose) {
  mobileClose.addEventListener('click', function(e) {
    e.stopPropagation();
    closeMobileMenu();
  });
}

// Close mobile menu when clicking outside
if (mobileMenu && mobileToggle) {
  document.addEventListener('click', function(e) {
    if (mobileMenuOpen && !mobileMenu.contains(e.target) && !mobileToggle.contains(e.target)) {
      closeMobileMenu();
    }
  });
}

// Close mobile menu on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && mobileMenuOpen) {
    closeMobileMenu();
    // Return focus to toggle
    if (mobileToggle) {
      mobileToggle.focus();
    }
  }
});

// Close mobile menu when clicking a nav link
const mobileNavLinks = document.querySelectorAll('.mobile-nav-link');
mobileNavLinks.forEach(link => {
  link.addEventListener('click', function() {
    closeMobileMenu();
  });
});

// ============================================
// MOBILE SUBMENUS
// ============================================
const submenuToggles = document.querySelectorAll('.submenu-toggle');

submenuToggles.forEach(toggle => {
  const submenuId = toggle.getAttribute('aria-controls');
  const submenu = submenuId ? document.getElementById(submenuId) : null;
  
  if (toggle && submenu) {
    // Toggle submenu
    toggle.addEventListener('click', function(e) {
      e.stopPropagation();
      const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
      
      if (isExpanded) {
        toggle.setAttribute('aria-expanded', 'false');
        submenu.classList.remove('active');
      } else {
        // Close other submenus
        closeAllSubmenus();
        toggle.setAttribute('aria-expanded', 'true');
        submenu.classList.add('active');
      }
    });
    
    // Close submenu when clicking a link
    const submenuLinks = submenu.querySelectorAll('.mobile-submenu-link');
    submenuLinks.forEach(link => {
      link.addEventListener('click', function() {
        closeMobileMenu();
      });
    });
  }
});

// Keyboard navigation for mobile submenus
document.addEventListener('keydown', function(e) {
  const activeSubmenuToggle = document.querySelector('.submenu-toggle[aria-expanded="true"]');
  if (activeSubmenuToggle) {
    const submenuId = activeSubmenuToggle.getAttribute('aria-controls');
    const submenu = submenuId ? document.getElementById(submenuId) : null;
    const links = submenu ? submenu.querySelectorAll('.mobile-submenu-link') : [];
    
    if (submenu && links.length > 0) {
      let currentIndex = -1;
      links.forEach((link, index) => {
        if (document.activeElement === link) {
          currentIndex = index;
        }
      });
      
      if (currentIndex >= 0) {
        if (e.key === 'ArrowDown' && currentIndex < links.length - 1) {
          e.preventDefault();
          links[currentIndex + 1].focus();
        } else if (e.key === 'ArrowUp' && currentIndex > 0) {
          e.preventDefault();
          links[currentIndex - 1].focus();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          activeSubmenuToggle.setAttribute('aria-expanded', 'false');
          submenu.classList.remove('active');
          activeSubmenuToggle.focus();
        }
      }
    }
  }
});

// ============================================
// DESKTOP DROPDOWNS
// ============================================
const dropdownToggles = document.querySelectorAll('.dropdown-toggle');

dropdownToggles.forEach(toggle => {
  const dropdown = toggle.closest('.dropdown');
  const menu = dropdown ? dropdown.querySelector('.dropdown-menu') : null;
  
  if (toggle && menu) {
    // Mouse enter/leave for desktop
    dropdown.addEventListener('mouseenter', function() {
      if (window.innerWidth > 768) {
        toggle.setAttribute('aria-expanded', 'true');
        menu.classList.add('active');
      }
    });
    
    dropdown.addEventListener('mouseleave', function() {
      if (window.innerWidth > 768) {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.remove('active');
      }
    });
    
    // Click for touch devices
    toggle.addEventListener('click', function(e) {
      if (window.innerWidth <= 768) {
        e.preventDefault();
        const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
        closeAllDropdowns();
        toggle.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
        menu.classList.toggle('active', !isExpanded);
      }
    });
  }
});

// Close all desktop dropdowns
function closeAllDropdowns() {
  dropdownToggles.forEach(toggle => {
    toggle.setAttribute('aria-expanded', 'false');
    const dropdown = toggle.closest('.dropdown');
    const menu = dropdown ? dropdown.querySelector('.dropdown-menu') : null;
    if (menu) {
      menu.classList.remove('active');
    }
  });
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
  if (window.innerWidth > 768) {
    const dropdowns = document.querySelectorAll('.dropdown');
    let clickedInsideDropdown = false;
    
    dropdowns.forEach(dropdown => {
      if (dropdown.contains(e.target)) {
        clickedInsideDropdown = true;
      }
    });
    
    if (!clickedInsideDropdown) {
      closeAllDropdowns();
    }
  }
});

// Close dropdowns on Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeAllDropdowns();
  }
});

// Keyboard navigation for dropdowns
document.addEventListener('keydown', function(e) {
  const activeDropdown = document.querySelector('.dropdown-toggle[aria-expanded="true"]');
  if (activeDropdown && window.innerWidth > 768) {
    const dropdown = activeDropdown.closest('.dropdown');
    const menu = dropdown ? dropdown.querySelector('.dropdown-menu') : null;
    const items = menu ? menu.querySelectorAll('.dropdown-item') : [];
    
    if (menu && items.length > 0) {
      let currentIndex = -1;
      items.forEach((item, index) => {
        if (document.activeElement === item) {
          currentIndex = index;
        }
      });
      
      if (currentIndex >= 0) {
        if (e.key === 'ArrowDown' && currentIndex < items.length - 1) {
          e.preventDefault();
          items[currentIndex + 1].focus();
        } else if (e.key === 'ArrowUp' && currentIndex > 0) {
          e.preventDefault();
          items[currentIndex - 1].focus();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          activeDropdown.setAttribute('aria-expanded', 'false');
          menu.classList.remove('active');
          activeDropdown.focus();
        }
      }
    }
  }
});

// ============================================
// SMOOTH SCROLL
// ============================================
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

// ============================================
// SCROLL EFFECTS
// ============================================
const header = document.querySelector('.site-header');

if (header) {
  let lastScrollY = window.scrollY;
  
  window.addEventListener('scroll', function() {
    const scrollY = window.scrollY;
    
    // Add scrolled class
    if (scrollY > 10) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
    
    lastScrollY = scrollY;
  });
}

// ============================================
// ACCESSIBILITY
// ============================================

// Add focus styles for keyboard navigation
document.addEventListener('DOMContentLoaded', function() {
  // Add tabindex to all interactive elements that don't have it
  const interactiveElements = document.querySelectorAll('a[href], button, [role="menuitem"], [role="option"]');
  interactiveElements.forEach(function(el) {
    if (!el.hasAttribute('tabindex')) {
      el.setAttribute('tabindex', '0');
    }
  });
});

// ============================================
// LAZY LOADING
// ============================================
if ('IntersectionObserver' in window) {
  const lazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]');
  
  const imageObserver = new IntersectionObserver(function(entries, observer) {
    entries.forEach(function(entry) {
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
  }, {
    rootMargin: '100px 0px',
    threshold: 0.01
  });
  
  lazyImages.forEach(function(img) {
    imageObserver.observe(img);
  });
}

// ============================================
// CONSOLE MESSAGE
// ============================================
console.log('%c🚀 NGUYỄN TÚ BLOG', 'color: #007AFF; font-size: 24px; font-weight: bold;');
console.log('%cPremium Ultra Version', 'color: #888; font-size: 12px;');
console.log('%cApple-inspired Premium Design', 'color: #007AFF; font-size: 10px;');

// ============================================
// INITIALIZE
// ============================================
// Close all menus on initial load
document.addEventListener('DOMContentLoaded', function() {
  closeAllDropdowns();
  closeAllSubmenus();
  
  // Set initial mobile menu state
  if (mobileToggle) {
    mobileToggle.setAttribute('aria-expanded', 'false');
  }
  
  // Set initial dropdown states
  dropdownToggles.forEach(toggle => {
    toggle.setAttribute('aria-expanded', 'false');
  });
  
  submenuToggles.forEach(toggle => {
    toggle.setAttribute('aria-expanded', 'false');
  });
});

// Handle window resize
window.addEventListener('resize', function() {
  // Close mobile menu on resize to desktop
  if (window.innerWidth > 768 && mobileMenuOpen) {
    closeMobileMenu();
  }
  
  // Close all dropdowns on resize
  closeAllDropdowns();
  closeAllSubmenus();
});

// ============================================
// EXPORT FOR DEBUGGING
// ============================================
window.NguyenTuBlog = {
  openMobileMenu,
  closeMobileMenu,
  toggleMobileMenu,
  closeAllDropdowns,
  closeAllSubmenus
};
