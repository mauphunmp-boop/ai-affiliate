import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NotificationProvider, useNotify } from '../../components/NotificationProvider.jsx';

function Demo() {
  const notify = useNotify();
  return (
    <div>
      <button onClick={()=>{ notify('info','A'); notify('info','A'); notify('info','B'); }}>Push</button>
    </div>
  );
}

describe('NotificationProvider queue & dedupe', () => {
  it('hiển thị lần lượt và bỏ qua thông báo trùng lặp gần', async () => {
    render(<NotificationProvider autoHideDuration={300}><Demo /></NotificationProvider>);
    await userEvent.click(screen.getByText('Push'));
    // Thông báo đầu tiên A
    expect(await screen.findByText('A')).toBeInTheDocument();
    // đợi auto hide
    await new Promise(r=>setTimeout(r, 350));
    // Thông báo tiếp theo phải là B (A duplicate bị bỏ)
    expect(await screen.findByText('B')).toBeInTheDocument();
  });
});
