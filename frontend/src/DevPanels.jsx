import React from 'react';

let CacheStatsPanelLazy = null;

export default function DevPanels() {
  const [showCache, setShowCache] = React.useState(false);
  const toggle = () => {
    if (!CacheStatsPanelLazy) {
      CacheStatsPanelLazy = React.lazy(()=>import('./components/CacheStatsPanel.jsx'));
    }
    setShowCache(s=>!s);
  };
  if (process.env.NODE_ENV === 'production') return null;
  return (
    <>
      <button
        style={{ position:'fixed', bottom:8, left:8, zIndex:1300, background:'#1976d2', color:'#fff', border:'none', padding:'4px 10px', borderRadius:4, cursor:'pointer', fontSize:12 }}
        onClick={toggle}
        aria-label="Toggle dev cache panel"
      >{showCache ? 'Hide Dev' : 'Dev Tools'}</button>
      {showCache && CacheStatsPanelLazy && (
        <React.Suspense fallback={null}>
          <CacheStatsPanelLazy />
        </React.Suspense>
      )}
    </>
  );
}
