import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography } from '@mui/material';
import { useT } from '../i18n/I18nProvider.jsx';

export default function ConfirmDialog({ open, title, message, onClose, onConfirm, confirmText, cancelText, loading=false, danger=false }) {
  const { t } = useT();
  const finalTitle = title || t('confirm_title');
  const finalConfirm = confirmText || t('confirm_ok');
  const finalCancel = cancelText || t('confirm_cancel');
  return (
    <Dialog open={open} onClose={() => !loading && onClose?.()} maxWidth="xs" fullWidth>
      <DialogTitle>{finalTitle}</DialogTitle>
      {message && (
        <DialogContent>
          <Typography variant="body2" sx={{ whiteSpace:'pre-wrap' }}>{message}</Typography>
        </DialogContent>
      )}
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>{finalCancel}</Button>
        <Button variant="contained" color={danger? 'error':'primary'} onClick={onConfirm} disabled={loading}>{finalConfirm}</Button>
      </DialogActions>
    </Dialog>
  );
}
