import React from 'react';
import './processShim.js';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './index.css';

import AppLayout from './layout/AppLayout.jsx';
import ReactLazyPreload from './utils/ReactLazyPreload.js';
const DashboardPage = ReactLazyPreload(()=>import('./pages/Dashboard/Dashboard.jsx'));
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
const IngestWizardPage = ReactLazyPreload(()=>import('./pages/Ingest/IngestWizard.jsx'));
const APIConfigsPage = ReactLazyPreload(()=>import('./pages/System/APIConfigsPage.jsx'));
const CampaignsDashboard = ReactLazyPreload(()=>import('./pages/Campaigns/CampaignsDashboard.jsx'));
const LinksManager = ReactLazyPreload(()=>import('./pages/Links/LinksManager.jsx'));
const MetricsPage = ReactLazyPreload(()=>import('./pages/Metrics/MetricsPage.jsx'));
const PerfDashboard = ReactLazyPreload(()=>import('./pages/Metrics/PerfDashboard.jsx'));
const NotFound = ReactLazyPreload(()=>import('./pages/NotFound.jsx'));
import ErrorBoundary from './components/ErrorBoundary.jsx';
import OfflineBanner from './components/OfflineBanner.jsx';
import { NotificationProvider, useNotify } from './components/NotificationProvider.jsx';
import { ColorModeProvider } from './context/ColorModeContext.jsx';
import { I18nProvider } from './i18n/I18nProvider.jsx';
import { initWebVitals } from './utils/webVitals.js';
import { submitWebVitals } from './api.js';
import { __registerNotifier } from './api.js';
// DevPanels tách ra file riêng để test không trigger createRoot
import DevPanels from './DevPanels.jsx';

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
  { index: true, element: suspense(<DashboardPage />) },
  { path: 'dashboard', element: suspense(<DashboardPage />) },
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
  { path: 'metrics/perf', element: suspense(<PerfDashboard />) },
      { path: 'ingest', element: suspense(<IngestOpsPage />) },
  { path: 'ingest/wizard', element: suspense(<IngestWizardPage />) },
      { path: 'ai', element: suspense(<AIAssistantPage />) },
  { path: 'system/health', element: suspense(<HealthPage />) },
  { path: 'system/logs', element: suspense(<LogsViewerPage />) },
      { path: '*', element: suspense(<NotFound />) },
  // legacy App removed from navigation/routes
    ]
  }
]);

// Register global preloader map & web vitals (skip khi TEST để tăng tốc & tránh side-effects)
if (typeof window !== 'undefined' && !import.meta.env.TEST) {
  window.__routePreloaders = {
    DashboardPage: () => DashboardPage.preload?.(),
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
    PerfDashboard: () => PerfDashboard.preload?.(),
    NotFound: () => NotFound.preload?.(),
    IngestOpsPage: () => IngestOpsPage.preload?.(),
    // legacy App removed
  };
  const idlePrefetch = () => {
    ['OffersListPage','TemplatesPage','ConvertTool','ExcelImportPage','ExcelExportPage','IngestOpsPage','AIAssistantPage','HealthPage'].forEach(k => { try { window.__routePreloaders[k]?.(); } catch {} });
  };
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(() => setTimeout(idlePrefetch, 1500));
  } else {
    setTimeout(idlePrefetch, 2500);
  }
  initWebVitals(
    (metric) => { try { console.debug('[Vitals]', metric.name, metric.value); } catch {} },
    (batch) => submitWebVitals(batch)
  );
}

// (DevPanels exported from separate file)

// Trong môi trường test (import.meta.env.TEST=true) tránh mount thật vào DOM global để hạn chế side-effects
// và ngăn khả năng giữ open handle không cần thiết nếu test vô tình import main.jsx.
if (!import.meta.env.TEST) {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <I18nProvider initial='vi'>
      <ColorModeProvider>
        <NotificationProvider>
          <NotifierRegistrar />
          <OfflineBanner />
          <ErrorBoundary>
            <RouterProvider router={router} />
          </ErrorBoundary>
          <DevPanels />
        </NotificationProvider>
      </ColorModeProvider>
    </I18nProvider>
  );
}


