import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './index.css';

import AppLayout from './layout/AppLayout.jsx';
import ReactLazyPreload from './utils/ReactLazyPreload.js';
const ShortlinksPage = ReactLazyPreload(()=>import('./pages/Affiliate/ShortlinksPage.jsx'));
const ConvertTool = ReactLazyPreload(()=>import('./pages/Affiliate/ConvertTool.jsx'));
const TemplatesPage = ReactLazyPreload(()=>import('./pages/Affiliate/TemplatesPage.jsx'));
const OffersListPage = ReactLazyPreload(()=>import('./pages/Offers/OffersListPage.jsx'));
const ExcelImportPage = ReactLazyPreload(()=>import('./pages/Offers/ExcelImportPage.jsx'));
const ExcelExportPage = ReactLazyPreload(()=>import('./pages/Offers/ExcelExportPage.jsx'));
const AIAssistantPage = ReactLazyPreload(()=>import('./pages/AI/AIAssistantPage.jsx'));
const HealthPage = ReactLazyPreload(()=>import('./pages/System/HealthPage.jsx'));
const LogsViewerPage = ReactLazyPreload(()=>import('./pages/System/LogsViewerPage.jsx'));
const IngestOpsPage = ReactLazyPreload(()=>import('./pages/Ingest/IngestOpsPage.jsx'));
const APIConfigsPage = ReactLazyPreload(()=>import('./pages/System/APIConfigsPage.jsx'));
const CampaignsDashboard = ReactLazyPreload(()=>import('./pages/Campaigns/CampaignsDashboard.jsx'));
const LinksManager = ReactLazyPreload(()=>import('./pages/Links/LinksManager.jsx'));
const MetricsPage = ReactLazyPreload(()=>import('./pages/Metrics/MetricsPage.jsx'));
import ErrorBoundary from './components/ErrorBoundary.jsx';
import OfflineBanner from './components/OfflineBanner.jsx';
import { NotificationProvider, useNotify } from './components/NotificationProvider.jsx';
import { ColorModeProvider } from './context/ColorModeContext.jsx';
import { I18nProvider } from './i18n/I18nProvider.jsx';
import { initWebVitals } from './utils/webVitals.js';
import { submitWebVitals } from './api.js';
import { __registerNotifier } from './api.js';

function NotifierRegistrar() {
  const enqueue = useNotify();
  React.useEffect(() => { __registerNotifier(enqueue); }, [enqueue]);
  return null;
}

const suspense = (el) => <React.Suspense fallback={<div style={{ padding:16 }}>Đang tải...</div>}>{el}</React.Suspense>;
const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: suspense(<ShortlinksPage />) },
      { path: 'affiliate/shortlinks', element: suspense(<ShortlinksPage />) },
      { path: 'affiliate/convert', element: suspense(<ConvertTool />) },
      { path: 'affiliate/templates', element: suspense(<TemplatesPage />) },
  { path: 'links', element: suspense(<LinksManager />) },
      { path: 'offers', element: suspense(<OffersListPage />) },
      { path: 'offers/excel/import', element: suspense(<ExcelImportPage />) },
      { path: 'offers/excel/export', element: suspense(<ExcelExportPage />) },
  { path: 'campaigns', element: suspense(<CampaignsDashboard />) },
  { path: 'system/api-configs', element: suspense(<APIConfigsPage />) },
  { path: 'metrics', element: suspense(<MetricsPage />) },
      { path: 'ingest', element: suspense(<IngestOpsPage />) },
      { path: 'ai', element: suspense(<AIAssistantPage />) },
  { path: 'system/health', element: suspense(<HealthPage />) },
  { path: 'system/logs', element: suspense(<LogsViewerPage />) },
  // legacy App removed from navigation/routes
    ]
  }
]);

// Register global preloader map for hover/focus route prefetch
if (typeof window !== 'undefined') {
  window.__routePreloaders = {
    ShortlinksPage: () => ShortlinksPage.preload?.(),
    ConvertTool: () => ConvertTool.preload?.(),
    TemplatesPage: () => TemplatesPage.preload?.(),
    OffersListPage: () => OffersListPage.preload?.(),
    ExcelImportPage: () => ExcelImportPage.preload?.(),
    ExcelExportPage: () => ExcelExportPage.preload?.(),
    AIAssistantPage: () => AIAssistantPage.preload?.(),
  HealthPage: () => HealthPage.preload?.(),
  LogsViewerPage: () => LogsViewerPage.preload?.(),
  APIConfigsPage: () => APIConfigsPage.preload?.(),
  CampaignsDashboard: () => CampaignsDashboard.preload?.(),
  LinksManager: () => LinksManager.preload?.(),
  MetricsPage: () => MetricsPage.preload?.(),
    IngestOpsPage: () => IngestOpsPage.preload?.(),
    // legacy App removed
  };
  // Idle prefetch after short delay
  const idlePrefetch = () => {
    ['OffersListPage','TemplatesPage','ConvertTool','ExcelImportPage','ExcelExportPage','IngestOpsPage','AIAssistantPage','HealthPage'].forEach(k => { try { window.__routePreloaders[k]?.(); } catch {} });
  };
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(() => setTimeout(idlePrefetch, 1500));
  } else {
    setTimeout(idlePrefetch, 2500);
  }
}

if (typeof window !== 'undefined') {
  initWebVitals(
    (metric) => { try { console.debug('[Vitals]', metric.name, metric.value); } catch {} },
    (batch) => submitWebVitals(batch)
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <I18nProvider initial='vi'>
    <ColorModeProvider>
      <NotificationProvider>
        <NotifierRegistrar />
        <OfflineBanner />
        <ErrorBoundary>
          <RouterProvider router={router} />
        </ErrorBoundary>
      </NotificationProvider>
    </ColorModeProvider>
  </I18nProvider>
);


