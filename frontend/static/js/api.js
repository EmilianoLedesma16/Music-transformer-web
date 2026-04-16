/**
 * API client para ByteBeat.
 * Requiere auth.js cargado primero (usa apiFetch).
 */
const API = {

  async process(formData) {
    return apiFetch('/process', { method: 'POST', body: formData });
  },

  async getJob(jobId) {
    return apiFetch(`/process/${jobId}`);
  },

  async getCreaciones() {
    return apiFetch('/creaciones');
  },

  async deleteCreacion(id) {
    return apiFetch(`/creaciones/${id}`, { method: 'DELETE' });
  },
};
