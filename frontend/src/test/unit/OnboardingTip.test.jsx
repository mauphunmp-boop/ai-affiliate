import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OnboardingTip from '../../components/OnboardingTip.jsx';

describe('OnboardingTip', () => {
  it('ẩn sau khi bấm Bắt đầu', async () => {
    render(<OnboardingTip />);
    expect(screen.getByText(/Chào mừng/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name:/Bắt đầu/i }));
  });
});
