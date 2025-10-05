const API_BASE = import.meta.env.VITE_API_BASE_URL || window.__API_BASE__ || 'http://localhost:8000'
const AI_PROVIDER = import.meta.env.VITE_AI_PROVIDER || 'groq'

export async function aiSuggest(query) {
  // Dùng /ai/test để luôn trả 200 kể cả khi chưa có products trong DB
  const url = new URL('/ai/test', API_BASE)
  if (query && query.trim()) url.searchParams.set('query', query)
  if (AI_PROVIDER) url.searchParams.set('provider', AI_PROVIDER)
  const res = await fetch(url.toString(), { method: 'POST' })
  if (!res.ok) throw new Error(`AI suggest failed: ${res.status}`)
  return res.json()
}

export async function sendFeedback({ value, messageHash, messagePreview, sessionId }) {
  // Tận dụng endpoint metrics/web-vitals để lưu feedback mà không cần bảng mới
  const payload = {
    metrics: [
      {
        name: 'AI_CHAT_FEEDBACK',
        value,
        rating: value > 0 ? 'good' : 'poor',
        url: location.href,
        session_id: sessionId,
        extra: { messageHash, messagePreview }
      }
    ],
    client_ts: Date.now()
  }
  const res = await fetch(new URL('/metrics/web-vitals', API_BASE).toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(`feedback failed: ${res.status}`)
  return res.json()
}
