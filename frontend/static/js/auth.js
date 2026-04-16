/**
 * Auth helpers — manejo de JWT en localStorage.
 * Se carga en todas las páginas.
 */
const Auth = {
  TOKEN_KEY: 'bb_token',
  USER_KEY:  'bb_user',

  saveToken(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  getUser() {
    try { return JSON.parse(localStorage.getItem(this.USER_KEY)); } catch { return null; }
  },

  logout() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    window.location.href = '/index.html';
  },

  /** Redirige al login si no hay token. Llamar en páginas protegidas. */
  requireAuth() {
    if (!this.getToken()) {
      window.location.href = '/index.html';
      return false;
    }
    return true;
  },
};

// Leer token de la URL (redirect desde Google OAuth callback)
(function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    // Guardamos sólo el token; el user lo obtenemos en la siguiente llamada
    localStorage.setItem(Auth.TOKEN_KEY, token);
    // Limpiar el token de la URL sin recargar
    const clean = window.location.pathname;
    window.history.replaceState({}, '', clean);
  }
})();

// Mostrar nombre del usuario en el navbar si existe el elemento
(function () {
  const el = document.getElementById('navUser');
  if (el) {
    const user = Auth.getUser();
    if (user) el.textContent = user.name || user.email;
  }
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.addEventListener('click', () => Auth.logout());
})();

/**
 * Wrapper fetch que incluye automáticamente el header Authorization.
 * Uso: const res = await apiFetch('/process', { method:'POST', json: {...} })
 *      const res = await apiFetch('/process', { method:'POST', body: formData })
 */
async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = Auth.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let body = options.body;
  if (options.json) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.json);
  }

  return fetch(path, { ...options, headers, body });
}
