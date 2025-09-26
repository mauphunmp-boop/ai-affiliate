import api from '../api.js';

// ===== Templates =====
export const listAffiliateTemplates = () => api.get('/aff/templates');
export const upsertAffiliateTemplate = (payload) => api.post('/aff/templates/upsert', payload);
export const autoGenerateTemplates = (network='accesstrade') => api.post('/aff/templates/auto-from-campaigns', { network });
export const updateAffiliateTemplate = (id, payload) => api.put(`/aff/templates/${id}`, payload);
export const deleteAffiliateTemplate = (id) => api.delete(`/aff/templates/${id}`);

// ===== Convert =====
export const convertAffiliateLink = (payload) => api.post('/aff/convert', payload);
