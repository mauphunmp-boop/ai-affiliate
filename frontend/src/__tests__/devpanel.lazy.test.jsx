import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import DevPanels from '../DevPanels.jsx';

beforeAll(() => { process.env.NODE_ENV = 'development'; });

describe('DevPanels lazy toggle', () => {
  it('không render panel trước khi bấm và render sau toggle', async () => {
  render(<DevPanels />);
  const toggleBtn = screen.getByRole('button', { name: /toggle dev cache panel/i });
  expect(toggleBtn).toBeInTheDocument();
    // Panel text "Cache Stats" chưa xuất hiện
    expect(screen.queryByText(/Cache Stats/i)).toBeNull();
  fireEvent.click(toggleBtn);
    // chờ lazy import
    const panelTitle = await screen.findByText(/Cache Stats/i, {}, { timeout: 2000 });
    expect(panelTitle).toBeInTheDocument();
    // Toggle hide
  fireEvent.click(toggleBtn);
    // Sau hide panel biến mất
    expect(screen.queryByText(/Cache Stats/i)).toBeNull();
  });
});
