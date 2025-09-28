import React from 'react';
import { TextField, Tooltip } from '@mui/material';

export default function AdminKeyInput({ storageKey = 'admin_api_key' }) {
  const [value, setValue] = React.useState(() => localStorage.getItem(storageKey) || '');
  const onChange = (e) => {
    const v = e.target.value;
    setValue(v);
  try { localStorage.setItem(storageKey, v); } catch { /* noop */ }
  };
  return (
    <Tooltip title="Admin key (used for protected ops)">
      <TextField size="small" label="Admin Key" value={value} onChange={onChange} type="password" sx={{ width:170 }} />
    </Tooltip>
  );
}
