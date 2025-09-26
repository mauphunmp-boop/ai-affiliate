import React from 'react';
import { messages } from './messages.js';

const I18nContext = React.createContext({ t:(k)=>k, lang:'vi', setLang:()=>{} });
export function I18nProvider({ children, initial='vi' }) {
  const [lang, setLang] = React.useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('app_lang_v1');
      if (saved) return saved;
    }
    return initial;
  });
  React.useEffect(()=>{ try { localStorage.setItem('app_lang_v1', lang); } catch{} }, [lang]);
  const value = React.useMemo(()=>({
    lang,
    setLang,
    t: (key, vars) => {
      let msg = (messages[lang] && messages[lang][key]) || key;
      if (vars && typeof msg === 'string') {
        msg = msg.replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? vars[k] : `{${k}}`));
      }
      return msg;
    }
  }), [lang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
export const useT = () => React.useContext(I18nContext);
