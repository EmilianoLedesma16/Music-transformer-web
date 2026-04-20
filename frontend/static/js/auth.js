const Auth = (() => {
  const KEY = "bb_token";

  function saveToken(token) {
    localStorage.setItem(KEY, token);
  }

  function getToken() {
    return localStorage.getItem(KEY);
  }

  function clearToken() {
    localStorage.removeItem(KEY);
  }

  function isLoggedIn() {
    return !!getToken();
  }

  function requireAuth() {
    if (!isLoggedIn()) {
      window.location.href = "/index.html";
    }
  }

  function redirectIfLoggedIn() {
    if (isLoggedIn()) {
      window.location.href = "/dashboard.html";
    }
  }

  function authHeaders() {
    return { Authorization: `Bearer ${getToken()}` };
  }

  function logout() {
    clearToken();
    window.location.href = "/index.html";
  }

  return { saveToken, getToken, clearToken, isLoggedIn, requireAuth, redirectIfLoggedIn, authHeaders, logout };
})();
