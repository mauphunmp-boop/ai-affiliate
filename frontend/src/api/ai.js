import api from '../api.js';

export const aiSuggest = (query, provider='groq') =>
  api.post(`/ai/suggest?provider=${encodeURIComponent(provider)}&query=${encodeURIComponent(query)}`);
