// frontend/src/Suggest.jsx
import { useState } from "react";
import { Paper, Box, TextField, Button, Typography } from "@mui/material";
import { aiSuggest } from "./api";

export default function Suggest() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");

  const onAsk = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setAnswer("");
    try {
      const res = await aiSuggest(query);
      setAnswer(res.data?.suggestion || "(không có nội dung)");
    } catch (e) {
      setAnswer("Có lỗi khi gọi AI: " + (e?.message || "unknown"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Typography variant="h6">Tư vấn bằng AI (không cần ra web)</Typography>
      <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
        <TextField
          fullWidth
          label="Nhập nhu cầu (vd: điện thoại dưới 5 triệu, pin trâu...)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button variant="contained" onClick={onAsk} disabled={loading}>
          {loading ? "Đang tư vấn..." : "Hỏi AI"}
        </Button>
      </Box>
      {answer && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle1">Kết quả:</Typography>
          <Typography whiteSpace="pre-wrap">{answer}</Typography>
        </Box>
      )}
    </Paper>
  );
}
