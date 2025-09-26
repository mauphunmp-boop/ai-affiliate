import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useNotify } from './NotificationProvider.jsx';

export default function CopyButton({ value, size='small', title='Copy', onCopied, silent=false, successText='Đã copy', timeout=1500 }) {
  const notify = useNotify();
  const [copied, setCopied] = React.useState(false);
  const tRef = React.useRef(null);
  React.useEffect(()=>() => tRef.current && clearTimeout(tRef.current), []);
  const handle = () => {
    if (!value) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      tRef.current = setTimeout(()=>setCopied(false), timeout);
      if (!silent) notify('success', successText);
      onCopied && onCopied();
    }).catch(()=> { if (!silent) notify('error', 'Copy thất bại'); });
  };
  return (
    <span style={{ display:'inline-flex', alignItems:'center' }} aria-live="polite" aria-atomic="true">
      <Tooltip title={copied ? successText : title}>
        <IconButton size={size} onClick={handle} aria-label="copy">
          <ContentCopyIcon fontSize="inherit" />
        </IconButton>
      </Tooltip>
    </span>
  );
}
