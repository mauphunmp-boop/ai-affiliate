// frontend/src/ApiConfigManager.jsx
import { useEffect, useState } from "react";
import api from "./api";
import { TextField, Button, Typography, Box, Paper } from "@mui/material";

export default function ApiConfigManager() {
  const [configs, setConfigs] = useState([]);
  const [form, setForm] = useState({ name: "", base_url: "", api_key: "", model: "" });

  const fetchConfigs = async () => {
    const res = await api.get("/api-configs");
    setConfigs(res.data);
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleSave = async () => {
    await api.post("/api-configs/upsert", form);
    fetchConfigs();
    setForm({ name: "", base_url: "", api_key: "", model: "" });
  };

  return (
    <Paper sx={{ p: 2, mt: 2 }}>
      <Typography variant="h6">Quản lý API Configs</Typography>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mt: 2 }}>
        <TextField label="Tên" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
        <TextField label="Base URL" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} />
        <TextField label="API Key" type="password" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} />
        <TextField label="Model" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} />
        <Button variant="contained" onClick={handleSave}>Lưu</Button>
      </Box>

      <Typography variant="subtitle1" sx={{ mt: 3 }}>Danh sách configs:</Typography>
      {configs.map(c => (
        <Box key={c.id} sx={{ border: "1px solid #ccc", borderRadius: 1, p: 1, mt: 1 }}>
          <Typography><b>{c.name}</b> - {c.base_url} ({c.model})</Typography>
        </Box>
      ))}
    </Paper>
  );
}
