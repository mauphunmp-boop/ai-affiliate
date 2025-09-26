import { createTheme } from '@mui/material/styles';

export const LIGHT_PALETTE = {
  mode: 'light',
  primary: { main: '#2563eb' },
  secondary: { main: '#7c3aed' },
  error: { main: '#dc2626' },
  warning: { main: '#d97706' },
  info: { main: '#0ea5e9' },
  success: { main: '#16a34a' },
  background: { default: '#f7f9fb', paper: '#ffffff' }
};

export const DARK_PALETTE = {
  mode: 'dark',
  primary: { main: '#3b82f6' },
  secondary: { main: '#a855f7' }
};

export function buildTheme({ dark=false } = {}) {
  return createTheme({
    palette: dark ? DARK_PALETTE : LIGHT_PALETTE,
    shape: { borderRadius: 10 },
    typography: { fontFamily: 'Inter, Roboto, Helvetica, Arial, sans-serif', body2: { fontSize: 13.5 } },
    components: {
      MuiButton: { styleOverrides: { root: { textTransform: 'none', fontWeight: 500 } } },
      MuiTableHead: { styleOverrides: { root: { background: dark? '#1f2937' : '#f1f5f9' } } },
      MuiPaper: { styleOverrides: { root: { transition: 'background-color .2s' } } }
    }
  });
}
