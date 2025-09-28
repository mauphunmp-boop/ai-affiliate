import React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { render } from '@testing-library/react';

// Simple light theme for tests; can extend if needed
const theme = createTheme({
  palette: { mode: 'light' }
});

export function renderWithProviders(ui, options={}) {
  function Wrapper({ children }) {
    return <ThemeProvider theme={theme}>{children}</ThemeProvider>;
  }
  return render(ui, { wrapper: Wrapper, ...options });
}

export * from '@testing-library/react';
