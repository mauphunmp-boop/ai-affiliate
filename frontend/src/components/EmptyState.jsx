import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import InboxIcon from '@mui/icons-material/Inbox';

export default function EmptyState({ iconSize=42, title='Không có dữ liệu', description, actionLabel, onAction }) {
  return (
    <Box sx={{ py:5, textAlign:'center', color:'text.secondary' }}>
      <InboxIcon sx={{ fontSize: iconSize, mb:1, opacity:0.5 }} />
      <Typography variant="subtitle1" sx={{ mb:0.5 }}>{title}</Typography>
      {description && <Typography variant="body2" sx={{ mb:2 }}>{description}</Typography>}
      {actionLabel && onAction && <Button variant="contained" size="small" onClick={onAction}>{actionLabel}</Button>}
    </Box>
  );
}
