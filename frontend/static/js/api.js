const API = (() => {
  const BASE = "";

  async function request(method, path, body, isForm = false) {
    const headers = { ...Auth.authHeaders() };
    if (!isForm && body) headers["Content-Type"] = "application/json";

    const res = await fetch(BASE + path, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
      Auth.logout();
      return;
    }

    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try {
        const json = await res.json();
        detail = json.detail || detail;
      } catch {}
      throw new Error(detail);
    }

    if (res.status === 204) return null;
    return res.json();
  }

  const login = (email, password) =>
    request("POST", "/auth/login", { email, password });

  const register = (name, email, password) =>
    request("POST", "/auth/register", { name, email, password });

  const submitProcess = (formData) =>
    request("POST", "/process", formData, true);

  const pollJob = (jobId) =>
    request("GET", `/process/${jobId}`);

  const listCreaciones = () =>
    request("GET", "/creaciones");

  const deleteCreacion = (id) =>
    request("DELETE", `/creaciones/${id}`);

  const parsePrompt = (text) =>
    request("POST", "/parse-prompt", { text });

  const getMe = () =>
    request("GET", "/me");

  const adminListUsers = () =>
    request("GET", "/admin/users");

  const adminSetRole = (userId, role) =>
    request("PATCH", `/admin/users/${userId}/role`, { role });

  return {
    login, register, submitProcess, pollJob,
    listCreaciones, deleteCreacion, parsePrompt,
    getMe, adminListUsers, adminSetRole,
  };
})();
