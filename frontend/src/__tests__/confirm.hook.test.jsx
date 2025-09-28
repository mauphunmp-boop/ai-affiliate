import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { useConfirmAction } from '../hooks/useConfirmAction.jsx';

function Sample(){
  const { confirm, dialog } = useConfirmAction();
  return <div>
    <button onClick={()=>confirm({ title:'Del', message:'Delete?', onConfirm:()=>{ window.__delTest= (window.__delTest||0)+1; } })}>Open</button>
    {dialog}
  </div>;
}

describe('useConfirmAction', () => {
  it('runs onConfirm', () => {
    render(<Sample />);
    fireEvent.click(screen.getByText('Open'));
    fireEvent.click(screen.getByText(/OK|Confirm|Xác nhận/i));
    expect(window.__delTest).toBe(1);
  });
});
