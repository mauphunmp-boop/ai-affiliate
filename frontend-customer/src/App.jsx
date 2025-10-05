import React, { useMemo, useRef, useState, useEffect } from 'react'
import { aiSuggest, sendFeedback } from './api'

function useSessionId() {
  return useMemo(() => {
    const key = 'customer_session_id'
    let s = localStorage.getItem(key)
    if (!s) {
      s = Math.random().toString(36).slice(2) + Date.now().toString(36)
      localStorage.setItem(key, s)
    }
    return s
  }, [])
}

function linkify(text) {
  const urlRegex = /(https?:\/\/[^\s)]+)|(www\.[^\s)]+)/gi
  const parts = []
  let lastIndex = 0
  let match
  while ((match = urlRegex.exec(text)) !== null) {
    const start = match.index
    if (start > lastIndex) parts.push(text.slice(lastIndex, start))
    const raw = match[0]
    const href = raw.startsWith('http') ? raw : `https://${raw}`
    parts.push(<a key={start} href={href} target="_blank" rel="noopener noreferrer">{raw}</a>)
    lastIndex = start + raw.length
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return parts
}

export default function App() {
  const [messages, setMessages] = useState([]) // {role, content, ts, liked}
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const listRef = useRef(null)
  const sessionId = useSessionId()

  async function onSend(e) {
    e?.preventDefault()
    const q = input.trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: q, ts: Date.now() }])
    setBusy(true)
    try {
      const data = await aiSuggest(q)
      const text = (data && data.suggestion) || 'Xin lỗi, chưa có gợi ý.'
      setMessages((m) => [...m, { role: 'assistant', content: text, ts: Date.now() }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: 'Lỗi khi gọi AI. Vui lòng thử lại sau.', ts: Date.now() }])
    } finally {
      setBusy(false)
      setTimeout(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }), 50)
    }
  }

  async function onFeedback(idx, value) {
    const msg = messages[idx]
    if (!msg || msg.role !== 'assistant') return
    const messageHash = String(msg.content).slice(0, 200) // đơn giản hoá, đủ để nhận diện
    try {
      await sendFeedback({ value, messageHash, messagePreview: messageHash, sessionId })
      setMessages((m) => m.map((it, i) => i === idx ? { ...it, liked: value } : it))
    } catch (e) {
      // bỏ qua lỗi feedback để không làm phiền người dùng
    }
  }

  useEffect(() => {
    // welcome
    if (messages.length === 0) {
      setMessages([
        { role: 'assistant', content: 'Chào bạn 👋 Hãy hỏi gợi ý sản phẩm. Ví dụ: "tai nghe chống ồn dưới 2 triệu"', ts: Date.now() }
      ])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const wrap = {
    display: 'grid',
    gridTemplateRows: 'auto 1fr auto',
    height: '100svh',
    background: 'var(--bg, #0b0d10)',
    color: 'var(--fg, #e6edf3)',
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif'
  }
  const header = { padding: '14px 16px', borderBottom: '1px solid #20242c', position: 'sticky', top: 0, background: 'inherit', zIndex: 10 }
  const title = { fontSize: '14px', margin: 0, color: '#9fb0c3' }
  const chat = { overflow: 'auto', padding: '16px', paddingBottom: 'calc(16px + var(--kb, 0px))', display: 'flex', flexDirection: 'column', gap: 10 }
  const bubbleBase = { maxWidth: '860px', borderRadius: 12, padding: '10px 12px', whiteSpace: 'pre-wrap', lineHeight: 1.55 }
  const userRow = { display: 'flex', justifyContent: 'flex-end' }
  const userBubble = { ...bubbleBase, background: '#1f6feb', color: 'white', borderTopRightRadius: 4 }
  const botRow = { display: 'flex', justifyContent: 'flex-start' }
  const botBubble = { ...bubbleBase, background: '#151a21', border: '1px solid #1f232b', borderTopLeftRadius: 4 }
  const footer = { borderTop: '1px solid #20242c', padding: '12px max(env(safe-area-inset-left),12px) calc(12px + var(--kb, 0px)) max(env(safe-area-inset-right),12px)', background: 'inherit', position: 'sticky', bottom: 0 }
  const inputWrap = { display: 'flex', gap: 10, maxWidth: 900, margin: '0 auto' }
  const inputBox = { flex: 1, padding: '12px 14px', borderRadius: 10, border: '1px solid #2b3240', background: '#0e1116', color: '#e6edf3', outline: 'none' }
  const sendBtn = { padding: '12px 16px', borderRadius: 10, background: '#238636', color: 'white', border: 'none', opacity: busy || !input.trim() ? .6 : 1 }
  const fbRow = { marginTop: 8, display: 'flex', gap: 8, fontSize: 13 }

  return (
    <div style={wrap}>
      <header style={header}>
        <h1 style={title}>AI Affiliate Chat — Hỏi gợi ý sản phẩm, nhận link tiếp thị</h1>
      </header>

      <div ref={listRef} style={chat}>
        {messages.map((m, idx) => (
          <div key={idx} style={m.role === 'user' ? userRow : botRow}>
            <div style={m.role === 'user' ? userBubble : botBubble}>
              <div>{linkify(m.content)}</div>
              {m.role === 'assistant' && (
                <div style={fbRow}>
                  <button onClick={() => onFeedback(idx, 1)} disabled={m.liked === 1}>👍 Hữu ích</button>
                  <button onClick={() => onFeedback(idx, -1)} disabled={m.liked === -1}>👎 Chưa phù hợp</button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={onSend} style={footer}>
        <div style={inputWrap}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Nhập câu hỏi về sản phẩm..."
            style={inputBox}
            onFocus={() => setTimeout(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }), 100)}
          />
          <button type="submit" disabled={busy || !input.trim()} style={sendBtn}>
            {busy ? 'Đang gợi ý…' : 'Gửi'}
          </button>
        </div>
        <div style={{ maxWidth: 900, margin: '8px auto 0', color: '#8b98a5', fontSize: 12 }}>
          Các link trong câu trả lời có thể là link tiếp thị.
        </div>
      </form>
    </div>
  )
}
