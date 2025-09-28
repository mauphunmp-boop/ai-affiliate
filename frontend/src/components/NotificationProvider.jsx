import React, { createContext, useCallback, useContext, useState, useRef } from 'react';
import { Snackbar, Alert } from '@mui/material';

const NotificationContext = createContext({ enqueue: () => {} });

export function NotificationProvider({ children, autoHideDuration = 4200, maxQueue = 6, collapseNetworkErrorsMs = 2500, shiftDelay = 10, testImmediate = false }) {
  const [queue, setQueue] = useState([]); // pending items
  const [current, setCurrent] = useState(null);
  // removed lastMessages state (only ref used for dedupe)
  const [, setLastMessages] = useState([]); // giữ set cho debug có thể bật lại nếu cần
  const lastMessagesRef = useRef([]); // ref đồng bộ cho dedupe trong nhiều enqueue cùng tick

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

  const lastEnqueueRef = useRef({ msg:'', time:0 });
  // keep collapse window in ref so enqueue stable without extra deps
  const collapseMsRef = useRef(collapseNetworkErrorsMs);
  collapseMsRef.current = collapseNetworkErrorsMs;
  const enqueue = useCallback((typeOrObj, maybeMessage) => {
    let item;
    if (typeof typeOrObj === 'object' && typeOrObj !== null) {
      item = { type: typeOrObj.type || typeOrObj.variant || 'info', message: typeOrObj.message || typeOrObj.text || '' };
    } else {
      item = { type: typeOrObj || 'info', message: maybeMessage || '' };
    }
    if (!item.message) return;
    const now = Date.now();
    // Collapse network errors: nếu cùng message và trong khoảng collapseNetworkErrorsMs bỏ qua
    if (item.type === 'error' && lastEnqueueRef.current.msg === item.message && (now - lastEnqueueRef.current.time) < collapseMsRef.current) {
      return;
    }
    lastEnqueueRef.current = { msg:item.message, time:now };
    // Dedupe: nếu message đã xuất hiện 2 lần gần nhất thì bỏ qua
    // Dedupe đồng bộ: kiểm tra 2 message trước trong ref (không tính message hiện tại)
    const recent = lastMessagesRef.current;
    const shouldSkip = recent.slice(-2).includes(item.message);
    if (shouldSkip) return;
    // Ghi nhận message vào ref và state (state chỉ dùng cho debug nếu cần)
    lastMessagesRef.current = [...recent, item.message].slice(-4);
    setLastMessages(lastMessagesRef.current);
    setQueue(q => {
      const next = [...q, { id: Date.now() + Math.random(), ...item }];
      return next.slice(-maxQueue);
    });
  }, [maxQueue]);

  // Test hook: cho phép test queue quan sát nhanh mà không phụ thuộc vào animation Snackbar
  React.useEffect(() => {
    if (!(typeof window !== 'undefined' && import.meta.env?.TEST)) return;
    window.__TEST__notifyState = {
      get current() { return current; },
      get queue() { return queue; },
      shift,
      enqueue
    };
    return () => { try { delete window.__TEST__notifyState; } catch {} };
  }, [current, queue, shift, enqueue]);

  // Ở môi trường test ta muốn giới hạn tối đa timer treo: nếu TEST và !testImmediate thì cưỡng bức autoHideDuration rất nhỏ.
  const isTestEnv = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.TEST;
  const effectiveAutoHide = isTestEnv ? Math.min(50, autoHideDuration) : autoHideDuration;
  const effectiveShiftDelay = isTestEnv ? 0 : shiftDelay;

  return (
    <NotificationContext.Provider value={{ enqueue }}>
      {children}
  <Snackbar
    open={!!current}
    key={current?.id}
    autoHideDuration={effectiveAutoHide}
        onClose={(_, r) => {
          if (r === 'clickaway') return;
            setCurrent(null);
            if (testImmediate) {
              shift();
            } else {
              setTimeout(shift, effectiveShiftDelay);
            }
        }}
        // MUI v6 đôi khi không chuyển prop onExited trong môi trường test → dùng fallback timeout ở onClose
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        data-current-message={current?.message || ''}
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

// default export để tương thích import mặc định trong test cũ
export default NotificationProvider;
