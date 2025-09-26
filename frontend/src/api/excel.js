import api from '../api.js';

// Download full export (4 sheets) as Excel
export const downloadExportExcel = (params = {}) => {
  return api.get('/offers/export-excel', { params, responseType: 'blob' });
};

// Download template (4 sheets with 2 header rows)
export const downloadExportTemplate = () => {
  return api.get('/offers/export-template', { responseType: 'blob' });
};

// Import offers/products/campaigns/commissions/promotions from Excel file (.xlsx)
export const importOffersExcel = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/offers/import-excel', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
};
