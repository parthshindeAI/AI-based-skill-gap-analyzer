/* =====================================================
   SkillForge AI — Shared API Client & Auth Utilities
   Used by all HTML pages
   ===================================================== */

const API_BASE = window.location.origin && window.location.origin !== 'null'
  ? window.location.origin
  : 'http://127.0.0.1:8000';
const TOKEN_KEY = 'skillforge_token';
const AUTH_RETURN_KEY = 'skillforge_auth_return';
const STUDENT_ROUTES = new Set(['/dashboard', '/assessment', '/roadmap', '/resume']);
const STUDENT_PAGE_ROUTES = new Map([
  ['/app/dashboard.html', '/dashboard'],
  ['/app/assessment.html', '/assessment'],
  ['/app/roadmap.html', '/roadmap'],
  ['/app/resume.html', '/resume'],
]);

// ── HTTP helper ───────────────────────────────────────
async function apiFetch(path, method = 'GET', body = null) {
  const token = localStorage.getItem(TOKEN_KEY);
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
  if (body !== null) opts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch (err) {
    throw new Error(`Unable to reach backend at ${API_BASE}. Make sure the backend is running.`);
  }

  let data;
  try {
    data = await res.json();
  } catch (err) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Auth helpers ──────────────────────────────────────
async function getProfile() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  try {
    return await apiFetch('/api/profile');
  } catch {
    return null;
  }
}

async function handleLogin() {
  console.debug('handleLogin called');
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  if (!username || !password) { showAlert('error', 'Please fill in all fields.'); return; }
  try {
    const data = await apiFetch('/api/login', 'POST', { username, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    closeModal();
    showAlert('success', `✅ Welcome back, ${data.user.name}!`);
    setTimeout(() => { navigateTo(getPostAuthPath()); }, 700);
  } catch (e) {
    showAlert('error', '❌ ' + e.message);
  }
}

async function handleRegister() {
  console.debug('handleRegister called');
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const studentId = document.getElementById('reg-student-id').value.trim();
  const password = document.getElementById('reg-password').value;
  const role = document.getElementById('reg-role').value;

  if (!name || !email || !studentId || !password) { showAlert('error', 'Please fill in all required fields.'); return; }
  try {
    const data = await apiFetch('/api/register', 'POST', {
      name, email, student_id: studentId, password,
      target_role: role || null,
      current_skills: [],
      learning_goals: [],
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    closeModal();
    showAlert('success', `🎉 Account created! Welcome, ${data.user.name}!`);
    setTimeout(() => { navigateTo(getPostAuthPath()); }, 800);
  } catch (e) {
    showAlert('error', '❌ ' + e.message);
  }
}

function navigateTo(page) {
  const routeMap = {
    'index.html': '/',
    'dashboard.html': '/dashboard',
    'assessment.html': '/assessment',
    'roadmap.html': '/roadmap',
    'resume.html': '/resume',
  };
  const target = routeMap[page] || page;
  window.location.href = target.startsWith('/') ? target : `/${target}`;
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  navigateTo('/');
}

function setAuthReturnPath(path) {
  const requestedPath = path?.split('?')[0];
  const route = STUDENT_PAGE_ROUTES.get(requestedPath) || requestedPath;
  if (STUDENT_ROUTES.has(route)) {
    sessionStorage.setItem(AUTH_RETURN_KEY, route);
  }
}

function getPostAuthPath() {
  const route = sessionStorage.getItem(AUTH_RETURN_KEY);
  sessionStorage.removeItem(AUTH_RETURN_KEY);
  return STUDENT_ROUTES.has(route) ? route : '/dashboard';
}

function redirectToLogin(path = window.location.pathname) {
  setAuthReturnPath(path);
  window.location.replace('/app/?auth=login');
}

async function requireStudentSession() {
  const user = await getProfile();
  if (user) return user;
  redirectToLogin();
  return null;
}

function syncLandingAuthState(user) {
  const openAuthBtn = document.getElementById('open-auth');
  const heroSignup = document.getElementById('hero-signup');
  const navDashboard = document.getElementById('nav-dashboard');
  const navLogout = document.getElementById('nav-logout');
  const heroDashboard = document.getElementById('hero-dashboard');

  const loggedIn = !!user;
  if (openAuthBtn) openAuthBtn.style.display = loggedIn ? 'none' : 'inline-flex';
  if (heroSignup) heroSignup.style.display = loggedIn ? 'none' : 'inline-flex';
  if (navDashboard) navDashboard.style.display = loggedIn ? 'inline-flex' : 'none';
  if (navLogout) navLogout.style.display = loggedIn ? 'inline-flex' : 'none';
  if (heroDashboard) heroDashboard.style.display = loggedIn ? 'inline-flex' : 'none';

  if (navLogout) {
    navLogout.onclick = logout;
  }
}

window.openModal = openModal;
window.closeModal = closeModal;
window.switchTab = switchTab;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.logout = logout;
window.redirectToLogin = redirectToLogin;
window.requireStudentSession = requireStudentSession;

// ── Modal helpers ─────────────────────────────────────
let modalReturnFocus = null;

function openModal(tab = 'login') {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modalReturnFocus = document.activeElement;
  modal.inert = false;
  modal.setAttribute('aria-hidden', 'false');
  modal.classList.add('open');
  switchTab(tab);
  requestAnimationFrame(() => {
    const firstInput = document.querySelector(`#form-${tab} input, #form-${tab} select`);
    firstInput?.focus();
  });
}
function closeModal() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  modal.inert = true;
  if (modalReturnFocus instanceof HTMLElement && modalReturnFocus.isConnected) {
    modalReturnFocus.focus();
  }
}
function switchTab(tab) {
  ['login', 'register'].forEach(t => {
    const tabButton = document.getElementById(`tab-${t}`);
    const panel = document.getElementById(`form-${t}`);
    tabButton?.classList.toggle('active', t === tab);
    tabButton?.setAttribute('aria-selected', String(t === tab));
    if (panel) {
      panel.hidden = t !== tab;
      panel.style.display = t === tab ? 'block' : 'none';
    }
  });
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', () => {
  if (new URLSearchParams(window.location.search).get('auth') === 'login') {
    window.history.replaceState(null, '', window.location.pathname);
    openModal('login');
  }

  document.getElementById('auth-modal')?.addEventListener('click', function (e) {
    if (e.target === this) closeModal();
  });
  document.getElementById('auth-modal')?.addEventListener('keydown', (e) => {
    const modal = document.getElementById('auth-modal');
    if (e.key === 'Escape') {
      closeModal();
      return;
    }
    if (e.key !== 'Tab' || !modal) return;

    const focusable = [...modal.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]'
    )].filter(element => !element.closest('[hidden]'));
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
  document.getElementById('open-auth')?.addEventListener('click', () => openModal('login'));
  document.getElementById('hero-signup')?.addEventListener('click', () => openModal('register'));
  document.getElementById('login-submit')?.addEventListener('click', handleLogin);
  document.getElementById('register-submit')?.addEventListener('click', handleRegister);

  document.querySelectorAll('a[href="/dashboard"], a[href="/assessment"], a[href="/roadmap"], a[href="/resume"]')
    .forEach((link) => {
      link.addEventListener('click', (event) => {
        if (localStorage.getItem(TOKEN_KEY)) return;
        event.preventDefault();
        setAuthReturnPath(link.getAttribute('href'));
        openModal('login');
      });
    });

  // Session-aware home UI: hide Get Started when user is already logged in.
  getProfile().then((user) => {
    syncLandingAuthState(user);
  }).catch(() => {
    syncLandingAuthState(null);
  });
});

// ── Alert helpers ─────────────────────────────────────
function showAlert(type, msg) {
  const el = document.querySelector('#auth-modal #alert-area') || document.getElementById('alert-area');
  if (!el) return;
  el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
}
function clearAlert() {
  const el = document.querySelector('#auth-modal #alert-area') || document.getElementById('alert-area');
  if (el) el.innerHTML = '';
}
