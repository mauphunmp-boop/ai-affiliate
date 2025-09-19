import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

export default api;

// ====== Helpers cho Links ======
export const getLinks = () => api.get("/links");
export const createLink = (payload) => api.post("/links", payload);
export const updateLink = (id, payload) => api.put(`/links/${id}`, payload);
export const deleteLink = (id) => api.delete(`/links/${id}`);

// ====== Helpers cho API Configs ======
export const upsertApiConfig = (payload) => api.post("/api-configs/upsert", payload);
export const listApiConfigs = () => api.get("/api-configs");

// ====== AI Suggest ======
export const aiSuggest = (query, provider = "groq") =>
  api.post(`/ai/suggest?provider=${encodeURIComponent(provider)}&query=${encodeURIComponent(query)}`);

// Thêm sau đoạn trên (mới hoàn toàn) — ngay dưới phần "AI Suggest"
export const getOffers = (merchant) =>
  api.get(`/offers${merchant ? `?merchant=${encodeURIComponent(merchant)}` : ""}`);
