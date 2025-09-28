import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Không mock MUI để kiểm tra tương tác thật (Snackbar auto hide + nút close biểu tượng)

import { NotificationProvider, useNotify } from '../../components/NotificationProvider.jsx';

function Demo() { // vẫn giữ demo cho context, nhưng ta sẽ gọi hook test trực tiếp
  const notify = useNotify();
  return <button onClick={()=>{ notify('info','A'); notify('info','A'); notify('info','B'); }}>Push</button>;
}

describe('NotificationProvider queue & dedupe', () => {
  it('hiển thị lần lượt và bỏ qua thông báo trùng lặp gần', async () => {
    render(<NotificationProvider autoHideDuration={99999} shiftDelay={0} testImmediate><Demo /></NotificationProvider>);
    // Dùng test hook enqueue để kiểm soát đồng bộ
    window.__TEST__notifyState.enqueue('info','A');
    window.__TEST__notifyState.enqueue('info','A'); // dedupe skip
    window.__TEST__notifyState.enqueue('info','B');
    // Current phải là A
    await waitFor(() => expect(screen.getByText('A')).toBeInTheDocument());
    // Shift sang B
    window.__TEST__notifyState.shift();
    await waitFor(() => expect(screen.getByText('B')).toBeInTheDocument());
    expect(screen.queryByText('A')).not.toBeInTheDocument();
  });
});
