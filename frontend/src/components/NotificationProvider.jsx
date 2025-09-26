import React, { createContext, useCallback, useContext, useState } from 'react';
import { Snackbar, Alert } from '@mui/material';

const NotificationContext = createContext({ enqueue: () => {} });

export function NotificationProvider({ children, autoHideDuration = 4200, maxQueue = 6 }) {
  const [queue, setQueue] = useState([]); // pending items
  const [current, setCurrent] = useState(null);
  const [lastMessages, setLastMessages] = useState([]); // để dedupe gần đây

  const shift = useCallback(() => {
    setCurrent(null);
    setQueue(q => {
      if (!q.length) return q;
      const [head, ...rest] = q;
      setCurrent(head);
      return rest;
    });
  }, []);

  React.useEffect(() => {
    if (!current && queue.length) {
      const [head, ...rest] = queue;
      setCurrent(head);
      setQueue(rest);
    }
  }, [current, queue]);

  const enqueue = useCallback((typeOrObj, maybeMessage) => {
    let item;
    if (typeof typeOrObj === 'object' && typeOrObj !== null) {
      item = { type: typeOrObj.type || typeOrObj.variant || 'info', message: typeOrObj.message || typeOrObj.text || '' };
    } else {
      item = { type: typeOrObj || 'info', message: maybeMessage || '' };
    }
    if (!item.message) return;
    // Dedupe: nếu message đã xuất hiện 2 lần gần nhất thì bỏ qua
    setLastMessages(prev => {
      const next = [...prev, item.message].slice(-4);
      return next;
    });
    const shouldSkip = lastMessages.slice(-2).includes(item.message);
    if (shouldSkip) return;
    setQueue(q => {
      const next = [...q, { id: Date.now() + Math.random(), ...item }];
      return next.slice(-maxQueue);
    });
  }, [lastMessages, maxQueue]);

  return (
    <NotificationContext.Provider value={{ enqueue }}>
      {children}
      <Snackbar
        open={!!current}
        key={current?.id}
        autoHideDuration={autoHideDuration}
        onClose={(_, r) => { if (r === 'clickaway') return; setCurrent(null); }}
        onExited={shift}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          variant="filled"
          severity={current?.type || 'info'}
          onClose={() => setCurrent(null)}
          sx={{ boxShadow:3, maxWidth:480 }}
        >
          {current?.message}
        </Alert>
      </Snackbar>
    </NotificationContext.Provider>
  );
}

export function useNotify() {
  return useContext(NotificationContext).enqueue;
}
