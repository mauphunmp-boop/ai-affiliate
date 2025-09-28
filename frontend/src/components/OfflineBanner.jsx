import React from 'react';
import { Alert, Collapse, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useT } from '../i18n/I18nProvider.jsx';

export function useOnlineStatus(options = {}) {
  const { debounceMs = 400 } = options;
  const [online, setOnline] = React.useState(typeof navigator !== 'undefined' ? navigator.onLine : true);
  const timeoutRef = React.useRef();
  React.useEffect(() => {
    const apply = (val) => {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setOnline(val), debounceMs);
    };
    const up = () => apply(true);
    const down = () => apply(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => { clearTimeout(timeoutRef.current); window.removeEventListener('online', up); window.removeEventListener('offline', down); };
  }, [debounceMs]);
  return online;
}

function tSafe(t, key, fallback) {
  try {
    const v = t(key);
    if (!v || v === key) return fallback;
    return v;
  } catch { return fallback; }
}

export default function OfflineBanner() {
  const online = useOnlineStatus();
  const [dismissed, setDismissed] = React.useState(false);
  const { t } = useT();
  React.useEffect(()=>{ if (online) setDismissed(false); }, [online]);
  const show = !online && !dismissed;
  return (
    <Collapse in={show} unmountOnExit>
      <Alert severity="warning" sx={{ borderRadius:0 }} action={<IconButton aria-label="dismiss offline" color="inherit" size="small" onClick={()=>setDismissed(true)}><CloseIcon fontSize="inherit" /></IconButton>}>
        {tSafe(t,'offline_message','Mất kết nối mạng. Một số thao tác có thể không thành công.')}
      </Alert>
    </Collapse>
  );
}
