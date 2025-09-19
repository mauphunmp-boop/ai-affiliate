import React, { useState, useEffect } from "react";
import {
  Container,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
} from "@mui/material";
import { Add, Edit, Delete } from "@mui/icons-material";
import api from "./api";
import Suggest from "./Suggest";
import OfferList from "./OfferList";

export default function App() {
  const [links, setLinks] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingLink, setEditingLink] = useState(null);
  const [form, setForm] = useState({ name: "", url: "", affiliate_url: "" });

  // Load links
  useEffect(() => {
    fetchLinks();
  }, []);

  const fetchLinks = async () => {
    try {
      const res = await api.get("/links");
      setLinks(res.data);
    } catch (error) {
      console.error("Error fetching links:", error);
    }
  };

  const handleOpen = (link = null) => {
    if (link) {
      setEditingLink(link);
      setForm({
        name: link.name,
        url: link.url,
        affiliate_url: link.affiliate_url,
      });
    } else {
      setEditingLink(null);
      setForm({ name: "", url: "", affiliate_url: "" });
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setForm({ name: "", url: "", affiliate_url: "" });
  };

  const handleSave = async () => {
    try {
      if (editingLink) {
        await api.put(`/links/${editingLink.id}`, form);
      } else {
        await api.post("/links", form);
      }
      fetchLinks();
      handleClose();
    } catch (error) {
      console.error("Error saving link:", error);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm("Bạn có chắc chắn muốn xóa link này?")) {
      try {
        await api.delete(`/links/${id}`);
        fetchLinks();
      } catch (error) {
        console.error("Error deleting link:", error);
      }
    }
  };

  return (
    <Container sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        Affiliate Link Manager
      </Typography>
      
      {/* KHU VỰC TƯ VẤN AI */}
      <Suggest />
      
      <OfferList />
      
      <Button
        variant="contained"
        startIcon={<Add />}
        onClick={() => handleOpen()}
        sx={{ mb: 2 }}
      >
        Thêm Link
      </Button>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Tên</TableCell>
              <TableCell>URL</TableCell>
              <TableCell>Affiliate URL</TableCell>
              <TableCell>Hành động</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {links.map((link) => (
              <TableRow key={link.id}>
                <TableCell>{link.name}</TableCell>
                <TableCell>
                  <a href={link.url} target="_blank" rel="noreferrer">
                    {link.url}
                  </a>
                </TableCell>
                <TableCell>
                  <a href={link.affiliate_url} target="_blank" rel="noreferrer">
                    {link.affiliate_url}
                  </a>
                </TableCell>
                <TableCell>
                  <IconButton onClick={() => handleOpen(link)} color="primary">
                    <Edit />
                  </IconButton>
                  <IconButton
                    onClick={() => handleDelete(link.id)}
                    color="error"
                  >
                    <Delete />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
            {links.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  Chưa có link nào
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Dialog Form */}
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>
          {editingLink ? "Sửa Link" : "Thêm Link Mới"}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Tên"
            fullWidth
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            margin="dense"
            label="URL"
            fullWidth
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
          />
          <TextField
            margin="dense"
            label="Affiliate URL"
            fullWidth
            value={form.affiliate_url}
            onChange={(e) =>
              setForm({ ...form, affiliate_url: e.target.value })
            }
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Hủy</Button>
          <Button onClick={handleSave} variant="contained">
            Lưu
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
