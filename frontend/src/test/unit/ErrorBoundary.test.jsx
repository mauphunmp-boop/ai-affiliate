import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../../components/ErrorBoundary.jsx';
import React from 'react';

function Boom(){
  throw new Error('Kaboom');
}

describe('ErrorBoundary', () => {
  test('catches render error and can attempt reset', async () => {
    const user = userEvent.setup();
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByText(/Sự cố không mong muốn/)).toBeInTheDocument();
    expect(screen.getByText(/Kaboom/)).toBeInTheDocument();
    // Click reset (will rethrow and show again, but ensures button wired)
    await user.click(screen.getByRole('button', { name:/Thử tải lại khu vực/ }));
    expect(screen.getByText(/Sự cố không mong muốn/)).toBeInTheDocument();
  });
});
