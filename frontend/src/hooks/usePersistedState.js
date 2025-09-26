import { useState, useEffect, useRef } from 'react';

export default function usePersistedState(key, defaultValue, { parse = JSON.parse, serialize = JSON.stringify, debounce = 0 } = {}) {
  const initial = (() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) return defaultValue;
      return parse(raw);
    } catch {
      return defaultValue;
    }
  })();
  const [value, setValue] = useState(initial);
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) clearTimeout(ref.current);
    const run = () => {
      try { localStorage.setItem(key, serialize(value)); } catch {}
    };
    if (debounce > 0) ref.current = setTimeout(run, debounce); else run();
    return () => ref.current && clearTimeout(ref.current);
  }, [value, key, serialize, debounce]);
  return [value, setValue];
}
