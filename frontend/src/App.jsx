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
import { useNotify } from './components/NotificationProvider.jsx';
import { useT } from './i18n/I18nProvider.jsx';
import ConfirmDialog from './components/ConfirmDialog.jsx';
import Suggest from "./Suggest";
import OfferList from "./OfferList";

export default function App() {
  const notify = useNotify();
  const { t } = useT();
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
        notify('success', 'Đã cập nhật link');
      } else {
        await api.post("/links", form);
        notify('success', 'Đã tạo link');
      }
      fetchLinks();
      handleClose();
    } catch (error) {
      notify('error', error.normalized?.message || 'Lưu link thất bại');
    }
  };

  const [confirm, setConfirm] = useState({ open:false, id:null });
  const handleDelete = (id) => setConfirm({ open:true, id });
  const doDelete = async () => {
    const id = confirm.id;
    try {
      await api.delete(`/links/${id}`);
      notify('success', 'Đã xoá link');
      fetchLinks();
    } catch (error) {
      notify('error', error.normalized?.message || 'Xoá link thất bại');
    } finally { setConfirm({ open:false, id:null }); }
  };

  return (
    <Container sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        {t('links_title')}
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
        {t('links_add')}
      </Button>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('links_col_name')}</TableCell>
              <TableCell>URL</TableCell>
              <TableCell>Affiliate URL</TableCell>
              <TableCell>{t('col_actions')}</TableCell>
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
                  <IconButton onClick={() => handleDelete(link.id)} color="error"><Delete /></IconButton>
                </TableCell>
              </TableRow>
            ))}
            {links.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  {t('links_empty')}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Dialog Form */}
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>
          {editingLink ? t('links_edit_title') : t('links_create_title')}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label={t('links_field_name')}
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
          <Button onClick={handleClose}>{t('dlg_cancel')}</Button>
          <Button onClick={handleSave} variant="contained">
            {t('dlg_save')}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirm.open}
        title={t('links_delete_title')}
        message={t('links_delete_confirm')}
        onClose={() => setConfirm({ open:false, id:null })}
        onConfirm={doDelete}
        danger
        confirmText={t('action_delete')}
      />
    </Container>
  );
}
