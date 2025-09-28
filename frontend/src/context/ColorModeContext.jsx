import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { buildTheme } from '../theme.js';

const ColorModeCtx = createContext({ dark:false, mode:'light', toggle:()=>{}, cycle:()=>{} });

export function ColorModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    try { return localStorage.getItem('pref_color_mode_v2') || 'system'; } catch { return 'system'; }
  });
  const [systemDark, setSystemDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setSystemDark(e.matches);
    try { mq.addEventListener('change', handler); } catch { mq.addListener(handler); }
    return () => { try { mq.removeEventListener('change', handler); } catch { mq.removeListener(handler); } };
  }, []);
  const dark = mode === 'system' ? systemDark : (mode === 'dark');
  const toggle = () => setMode(m => (m === 'dark' ? 'light' : 'dark'));
  const cycle = () => setMode(m => (m === 'light' ? 'dark' : (m === 'dark' ? 'system' : 'light')));
  useEffect(()=>{ try { localStorage.setItem('pref_color_mode_v2', mode); } catch{} }, [mode]);
  const theme = useMemo(()=> buildTheme({ dark }), [dark]);
  const value = useMemo(()=>({ dark, mode, toggle, cycle, setMode }), [dark, mode]);
  return (
    <ColorModeCtx.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeCtx.Provider>
  );
}

export function useColorMode() {
  return useContext(ColorModeCtx);
}

export default ColorModeProvider;
