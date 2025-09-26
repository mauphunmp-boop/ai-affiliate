import React from 'react';
import { Alert, Collapse, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

export default function OfflineBanner() {
  const [online, setOnline] = React.useState(navigator.onLine);
  const [dismissed, setDismissed] = React.useState(false);
  React.useEffect(() => {
    const up = () => setOnline(true);
    const down = () => { setOnline(false); setDismissed(false); };
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => { window.removeEventListener('online', up); window.removeEventListener('offline', down); };
  }, []);
  const show = !online && !dismissed;
  return (
    <Collapse in={show} unmountOnExit>
      <Alert severity="warning" sx={{ borderRadius:0 }} action={<IconButton aria-label="dismiss offline" color="inherit" size="small" onClick={()=>setDismissed(true)}><CloseIcon fontSize="inherit" /></IconButton>}>
        Mất kết nối mạng. Một số thao tác có thể không thành công.
      </Alert>
    </Collapse>
  );
}
