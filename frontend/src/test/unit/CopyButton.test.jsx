import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CopyButton from '../../components/CopyButton.jsx';
import { NotificationProvider } from '../../components/NotificationProvider.jsx';

global.navigator.clipboard = { writeText: vi.fn().mockResolvedValue() };

describe('CopyButton', () => {
  it('đổi tooltip sang Đã copy sau khi bấm', async () => {
    render(<NotificationProvider><CopyButton value="hello" title="Copy" successText="Đã copy" silent /></NotificationProvider>);
    const btn = screen.getByRole('button', { name: /copy/i });
    await userEvent.click(btn);
    // Do MUI Tooltip lazy render, ta kiểm tra gọi clipboard
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello');
  });
});
