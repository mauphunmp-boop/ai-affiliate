import React, { useState, useEffect, useRef } from 'react';
import { Typography, Paper, Box, TextField, Button, MenuItem, IconButton, Tooltip, Divider, Stack, Chip } from '@mui/material';
import CopyButton from '../../components/CopyButton.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import { aiSuggest } from '../../api/ai';

// Lưu lịch sử ở localStorage để refresh không mất
const STORAGE_KEY = 'ai_chat_history_v1';

export default function AIAssistantPage() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('groq');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]); // {id, q, a, provider, t}
  const [answerStreaming, setAnswerStreaming] = useState('');
  const boxRef = useRef(null);

  // Load history
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setHistory(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0,200))); } catch {}
  }, [history]);

  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }, [history, answerStreaming]);

  const run = async () => {
    if (!query.trim() || loading) return;
    const q = query.trim();
    setLoading(true);
    setAnswerStreaming('');
    try {
      const res = await aiSuggest(q, provider);
      const ans = res.data?.suggestion || '(không có nội dung)';
      setHistory(h => [...h, { id: Date.now(), q, a: ans, provider, t: new Date().toISOString() }]);
      setQuery('');
    } catch (e) {
      setHistory(h => [...h, { id: Date.now(), q, a: 'Lỗi: ' + (e?.response?.data?.detail || e.message), provider, t: new Date().toISOString(), error:true }]);
    } finally {
      setLoading(false);
    }
  };

  const [confirm, setConfirm] = useState(false);
  const clearAll = () => setConfirm(true);
  const doClear = () => { setHistory([]); setConfirm(false); };

  const providers = [
    { value: 'groq', label: 'Groq (Mặc định)' },
    { value: 'openai', label: 'OpenAI (nếu cấu hình)' },
    { value: 'ollama', label: 'Ollama Local' },
  ];

  return (
    <Paper sx={{ p:2, display:'flex', flexDirection:'column', height:'100%', maxHeight:'calc(100vh - 140px)' }}>
      <Typography variant="h5" gutterBottom>AI Assistant</Typography>
      <Typography variant="body2" sx={{ mb:2 }}>
        Hỏi nhanh để được gợi ý sản phẩm, mô tả bán hàng hoặc ý tưởng nội dung. Lịch sử chỉ lưu cục bộ trình duyệt.
      </Typography>
      <Box component="form" onSubmit={e=>{ e.preventDefault(); run(); }} sx={{ display:'flex', gap:1, flexWrap:'wrap', mb:2 }}>
        <TextField
          fullWidth
            label="Câu hỏi / nhu cầu"
            value={query}
            onChange={e=>setQuery(e.target.value)}
            placeholder="Ví dụ: laptop văn phòng ~15tr pin tốt, hoặc: Viết caption Facebook về Black Friday"
        />
        <TextField select size="small" label="Provider" value={provider} onChange={e=>setProvider(e.target.value)} sx={{ minWidth:140 }}>
          {providers.map(p => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
        </TextField>
        <Button type="submit" variant="contained" startIcon={<PlayArrowIcon/>} disabled={loading}>{loading ? 'Đang hỏi...' : 'Hỏi'}</Button>
        <Button variant="text" color="error" startIcon={<DeleteSweepIcon/>} onClick={clearAll} disabled={!history.length}>Xoá lịch sử</Button>
      </Box>
      <Divider sx={{ mb:2 }} />
      <Box ref={boxRef} sx={{ flex:1, overflowY:'auto', pr:1, display:'flex', flexDirection:'column', gap:2 }}>
        {history.length === 0 && (
          <Typography variant="body2" color="text.secondary">Chưa có câu hỏi. Hãy nhập câu đầu tiên ở trên.</Typography>
        )}
        {history.map(item => (
          <Paper key={item.id} variant="outlined" sx={{ p:1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb:0.5, flexWrap:'wrap' }}>
              <Chip size="small" label={new Date(item.t).toLocaleTimeString()} />
              <Chip size="small" label={item.provider} color="primary" />
              {item.error && <Chip size="small" color="error" label="Lỗi" />}
              <CopyButton size="small" value={item.q} title="Copy câu hỏi" />
            </Stack>
            <Typography variant="subtitle2" sx={{ whiteSpace:'pre-wrap' }}>{item.q}</Typography>
            <Divider sx={{ my:1 }} />
            <Box sx={{ position:'relative' }}>
              <Typography variant="body2" sx={{ whiteSpace:'pre-wrap' }}>{item.a}</Typography>
              <Box sx={{ position:'absolute', top:0, right:0 }}>
                <CopyButton size="small" value={item.a} title="Copy trả lời" />
              </Box>
            </Box>
          </Paper>
        ))}
        {answerStreaming && (
          <Paper variant="outlined" sx={{ p:1.5 }}>
            <Typography variant="subtitle2">Đang nhận...</Typography>
            <Typography variant="body2" sx={{ whiteSpace:'pre-wrap' }}>{answerStreaming}</Typography>
          </Paper>
        )}
      </Box>
      <ConfirmDialog
        open={confirm}
        onClose={()=>setConfirm(false)}
        onConfirm={doClear}
        title="Xoá lịch sử"
        message="Bạn chắc chắn muốn xoá toàn bộ lịch sử AI?"/>
    </Paper>
  );
}
