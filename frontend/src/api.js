import axios from "axios";

let notifyHandler = null; // sẽ được đăng ký từ NotificationProvider khi khởi tạo app
export const __registerNotifier = (fn) => { notifyHandler = fn; };

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

function normalizeAxiosError(error) {
  if (!error) return { message: 'Lỗi không xác định' };
  if (error.response) {
    const d = error.response.data;
    const msg = d?.detail || d?.message || error.message || 'Lỗi máy chủ';
    return { message: msg, status: error.response.status, data: d };
  }
  if (error.request) return { message: 'Không nhận được phản hồi từ máy chủ', network: true };
  return { message: error.message || 'Lỗi không xác định' };
}

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const norm = normalizeAxiosError(err);
    err.normalized = norm;
    const status = norm.status;
    if (notifyHandler && (norm.network || (status && status >= 500))) {
      notifyHandler('error', norm.message);
    }
    return Promise.reject(err);
  }
);

export default api;

// ====== Helpers cho Links ======
export const getLinks = () => api.get("/links");
export const createLink = (payload) => api.post("/links", payload);
export const updateLink = (id, payload) => api.put(`/links/${id}`, payload);
export const deleteLink = (id) => api.delete(`/links/${id}`);

// ====== Helpers cho API Configs ======
export const upsertApiConfig = (payload) => api.post("/api-configs/upsert", payload);
export const listApiConfigs = () => api.get("/api-configs");
// Settings & policy helpers (link-check rotate config shares same flags storage)
export const setLinkcheckConfig = (payload={}) => api.post('/settings/linkcheck/config', payload);
export const getLinkcheckFlags = () => api.post('/settings/linkcheck/config'); // POST without body returns current flags

// ====== AI Suggest ======
export const aiSuggest = (query, provider = "groq") =>
  api.post(`/ai/suggest?provider=${encodeURIComponent(provider)}&query=${encodeURIComponent(query)}`);

// Thêm sau đoạn trên (mới hoàn toàn) — ngay dưới phần "AI Suggest"
// Offers: hỗ trợ phân trang (skip, limit) + merchant filter
export const getOffers = ({ merchant, page=1, pageSize=20 } = {}) => {
  const skip = (Math.max(1, page) - 1) * pageSize;
  const params = new URLSearchParams();
  params.set('skip', String(skip));
  params.set('limit', String(pageSize));
  if (merchant) params.set('merchant', merchant);
  return api.get(`/offers?${params.toString()}`);
};

// Affiliate convert (dùng cho Chatbot/UI trước khi render link)
export const affConvert = (payload) => api.post("/aff/convert", payload);

// ====== Metrics (Web Vitals) ======
export const submitWebVitals = (batch) => api.post('/metrics/web-vitals', batch);
