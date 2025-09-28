import React from 'react';
import ConfirmDialog from '../components/ConfirmDialog.jsx';

export function useConfirmAction() {
  const [state, setState] = React.useState({ open:false, title:'', message:'', onConfirm:null, confirmText:null, cancelText:null });
  const confirm = (opts={}) => setState({ open:true, title: opts.title||'Xác nhận', message: opts.message||'Bạn chắc chắn?', onConfirm: opts.onConfirm||(()=>{}), confirmText: opts.confirmText||null, cancelText: opts.cancelText||null });
  const handleClose = () => setState(s=>({ ...s, open:false }));
  const dialog = state.open ? (
    <ConfirmDialog
      open={state.open}
      title={state.title}
      content={state.message}
      confirmText={state.confirmText || 'OK'}
      cancelText={state.cancelText || 'Hủy'}
      onCancel={handleClose}
      onConfirm={()=>{ const fn = state.onConfirm; handleClose(); try { fn(); } catch {} }}
    />
  ) : null;
  return { confirm, dialog };
}
