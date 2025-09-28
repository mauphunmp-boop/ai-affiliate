import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Không mock MUI để kiểm tra tương tác thật (Snackbar auto hide + nút close biểu tượng)

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
    const user = userEvent.setup();
    render(<NotificationProvider autoHideDuration={999999} shiftDelay={0} testImmediate><Demo /></NotificationProvider>);
    await user.click(screen.getByText('Push'));
    expect(await screen.findByText('A')).toBeInTheDocument();
    // Click nút đóng (aria-label="Close") để kích hoạt shift thủ công
    const closeBtn = screen.getByRole('button', { name: /close/i });
    await user.click(closeBtn);
    await waitFor(() => expect(screen.getByText('B')).toBeInTheDocument());
    expect(screen.queryByText('A')).not.toBeInTheDocument();
  });
});
