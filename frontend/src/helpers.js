// src/helpers.js - GOOGLE LEVEL PREMIUM HELPERS (Animations, Accessibility)

export const smoothScrollTo = (elementId, offset = 0) => {
  const element = document.getElementById(elementId);
  if (element) {
    const position = element.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({ top: position, behavior: 'smooth' });
  }
};

export const formatDateLuxury = (date, format = 'long') => {
  const options = {
    short: { month: 'short', day: 'numeric', year: 'numeric' },
    long: { month: 'long', day: 'numeric', year: 'numeric' },
    full: { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' },
  };
  const dateObj = new Date(date);
  return isNaN(dateObj) ? 'Invalid Date' : new Intl.DateTimeFormat('en-US', options[format] || options.long).format(dateObj);
};

export const copyToClipboard = async (text, toastFunction) => {
  try {
    if (!navigator.clipboard || !window.isSecureContext) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(text);
    toastFunction?.('Copied!', 'success');
    return true;
  } catch (err) {
    toastFunction?.('Copy failed', 'error');
    return false;
  }
};

export const getViewportSize = () => ({
  width: window.innerWidth,
  height: window.innerHeight,
  isMobile: window.innerWidth < 768,
  isTablet: window.innerWidth >= 768 && window.innerWidth < 1024,
  isDesktop: window.innerWidth >= 1024,
});

export const generateId = (prefix = 'id') => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;

export const addRippleEffect = (event) => {
  const btn = event.currentTarget;
  const ripple = document.createElement('span');
  const dia = Math.max(btn.clientWidth, btn.clientHeight);
  const rad = dia / 2;
  ripple.style.width = ripple.style.height = `${dia}px`;
  ripple.style.left = `${event.clientX - btn.offsetLeft - rad}px`;
  ripple.style.top = `${event.clientY - btn.offsetTop - rad}px`;
  ripple.style.background = 'rgba(255,255,255,0.2)';
  ripple.style.position = 'absolute';
  ripple.style.borderRadius = '50%';
  ripple.style.transform = 'scale(0)';
  ripple.style.animation = 'ripple 0.6s linear';
  btn.appendChild(ripple);
  setTimeout(() => ripple.remove(), 600);
  const style = document.createElement('style');
  style.innerHTML = `@keyframes ripple { to { transform: scale(4); opacity: 0; } }`;
  document.head.appendChild(style);
};

export const animateNumber = (element, start, end, duration = 1000) => {
  if (!element) return;
  let startTime = null;
  const step = (timestamp) => {
    startTime ||= timestamp;
    const progress = Math.min((timestamp - startTime) / duration, 1);
    element.textContent = Math.floor(progress * (end - start) + start).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
};

export const lazyLoadImages = () => {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('img.lazy').forEach((img) => { if (img.dataset.src) img.src = img.dataset.src; img.classList.remove('lazy'); });
    return;
  }
  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const img = entry.target;
        if (img.dataset.src) img.src = img.dataset.src;
        img.classList.remove('lazy');
        obs.unobserve(img);
      }
    });
  });
  document.querySelectorAll('img.lazy').forEach((img) => observer.observe(img));
};

export const setTheme = (theme) => {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
};

export const getSavedTheme = () => {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  return saved || (prefersDark ? 'dark' : 'light');
};

export const initializeTheme = () => {
  const theme = getSavedTheme();
  setTheme(theme);
  return theme;
};

export const handleKeyboardNav = (event, callbacks) => {
  const handlers = {
    Enter: callbacks.onEnter,
    Escape: callbacks.onEscape,
    ArrowUp: callbacks.onArrowUp,
    ArrowDown: callbacks.onArrowDown,
    ArrowLeft: callbacks.onArrowLeft,
    ArrowRight: callbacks.onArrowRight,
    Tab: callbacks.onTab,
  };
  const key = event.key;
  if (handlers[key]) {
    event.preventDefault();
    handlers[key](event);
  }
};

export const createFocusTrap = (element) => {
  if (!element) return () => {};
  const focusables = element.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const handleTab = (e) => {
    if (e.key === 'Tab') {
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };
  if (focusables.length > 0) {
    element.addEventListener('keydown', handleTab);
    first.focus();
  }
  return () => element.removeEventListener('keydown', handleTab);
};

export const isInViewport = (element) => {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.top >= 0 && rect.left >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) && rect.right <= (window.innerWidth || document.documentElement.clientWidth);
};

export const initAnimateOnScroll = (className = 'animate-on-scroll') => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });
  document.querySelectorAll(`.${className}`).forEach((el) => observer.observe(el));
};