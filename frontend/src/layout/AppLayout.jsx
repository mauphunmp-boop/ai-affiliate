import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
// Consolidated MUI imports
import { AppBar, Toolbar, Typography, IconButton, Box, Drawer, List, ListItem, ListItemButton, ListItemText, useMediaQuery, Tooltip, Divider, Select, MenuItem } from '@mui/material';
import GettingStartedPanel from '../components/GettingStartedPanel.jsx';
import MenuIcon from '@mui/icons-material/Menu';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import OnboardingTip from '../components/OnboardingTip.jsx';
import { useColorMode } from '../context/ColorModeContext.jsx';
import { useT } from '../i18n/I18nProvider.jsx';

const drawerWidth = 230;

const baseNav = [
  { to: '/affiliate/shortlinks', labelKey: 'nav_shortlinks', key:'ShortlinksPage' },
  { to: '/links', labelKey: 'links_title', key:'LinksManager' },
  { to: '/affiliate/convert', labelKey: 'nav_convert', key:'ConvertTool' },
  { to: '/affiliate/templates', labelKey: 'nav_templates', key:'TemplatesPage' },
  { to: '/offers', labelKey: 'nav_offers', key:'OffersListPage' },
  { to: '/offers/excel/import', labelKey: 'nav_excel_import', key:'ExcelImportPage' },
  { to: '/offers/excel/export', labelKey: 'nav_excel_export', key:'ExcelExportPage' },
  { to: '/campaigns', labelKey: 'nav_campaigns', key:'CampaignsDashboard' },
  { to: '/system/api-configs', labelKey: 'nav_api_configs', key:'APIConfigsPage' },
  { to: '/metrics', labelKey: 'nav_metrics', key:'MetricsPage' },
  { to: '/ingest', labelKey: 'nav_ingest', key:'IngestOpsPage' },
  { to: '/ai', labelKey: 'nav_ai', key:'AIAssistantPage' },
  { to: '/system/health', labelKey: 'nav_health', key:'HealthPage' },
  { to: '/system/logs', labelKey: 'nav_logs', key:'LogsViewerPage' },
];

export default function AppLayout() {
  const { dark, mode, cycle } = useColorMode();
  const { t, lang, setLang } = useT();
    const navItems = React.useMemo(()=> baseNav.map(n => ({ ...n, label: t(n.labelKey) })), [t]);
  const isMobile = useMediaQuery(theme => theme.breakpoints.down('sm'));
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const toggleDrawer = () => setMobileOpen(o=>!o);
  const location = useLocation();
  // Lightweight debug for route changes (dev only)
  React.useEffect(()=>{ if (import.meta.env.DEV) { console.debug('[route-change]', location.pathname); } }, [location]);

  const drawerContent = (
    <Box sx={{ height:'100%', display:'flex', flexDirection:'column' }}>
      <Toolbar />
      <Divider />
      <Box sx={{ flex:1, overflow:'auto' }}>
        <List>
          {navItems.map(item => {
            const needEnd = item.to === '/offers';
            return (
              <ListItem key={item.to} disablePadding onClick={()=>{ if(isMobile) setMobileOpen(false); }}>
                <NavLink
                  to={item.to}
                  end={needEnd}
                  data-nav-item={item.to}
                  onMouseEnter={()=>window.__routePreloaders?.[item.key]?.()}
                  onFocus={()=>window.__routePreloaders?.[item.key]?.()}
                  style={{ flex:1, textDecoration:'none', color:'inherit' }}
                  className={({ isActive }) => isActive ? 'active navlink-wrapper' : 'navlink-wrapper'}
                >
                  <ListItemButton sx={{ '&.active, .active &': { backgroundColor: 'action.selected' } }}>
                    <ListItemText primary={item.label} />
                  </ListItemButton>
                </NavLink>
              </ListItem>
            );
          })}
        </List>
      </Box>
      <Box sx={{ p:1, textAlign:'center', typography:'caption', opacity:0.6 }}>v1 UI</Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <a href="#main-content" className="skip-link">{t('skip_to_content')}</a>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap:1 }}>
          {isMobile && (
            <IconButton color="inherit" edge="start" onClick={toggleDrawer} aria-label="open navigation"><MenuIcon /></IconButton>
          )}
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow:1 }}>
            AI Affiliate Dashboard
          </Typography>
          <Tooltip title={mode === 'system' ? (dark ? t('light_mode') : t('dark_mode')) : (mode==='dark'? t('light_mode') : t('dark_mode'))}>
            <IconButton color="inherit" onClick={cycle} aria-label="cycle color mode">
              {mode === 'system' ? <SettingsBrightnessIcon /> : (dark ? <LightModeIcon /> : <DarkModeIcon />)}
            </IconButton>
          </Tooltip>
          <Select size="small" value={lang} onChange={e=>setLang(e.target.value)} sx={{ color:'#fff', borderColor:'#fff', '& fieldset':{ borderColor:'rgba(255,255,255,0.4)' }, ml:1 }}>
            <MenuItem value="vi">VI</MenuItem>
            <MenuItem value="en">EN</MenuItem>
          </Select>
        </Toolbar>
      </AppBar>
      {isMobile ? (
        <Drawer variant="temporary" open={mobileOpen} onClose={toggleDrawer} ModalProps={{ keepMounted:true }}
          sx={{ '& .MuiDrawer-paper': { width: drawerWidth } }}>
          {drawerContent}
        </Drawer>
      ) : (
        <Drawer variant="permanent" sx={{ width: drawerWidth, flexShrink: 0, '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box' } }}>
          {drawerContent}
        </Drawer>
      )}
      <Box component="main" id="main-content" sx={{ flexGrow: 1, p: { xs:2, sm:3 } }}>
        <Toolbar />
          <GettingStartedPanel />
          <OnboardingTip />
        <RouteFocusWrapper>
          <Outlet />
        </RouteFocusWrapper>
      </Box>
    </Box>
  );
}

// Wrapper to auto-focus first h1/h2 after route changes for accessibility
function RouteFocusWrapper({ children }) {
  React.useEffect(() => {
    // Microtask to allow children render
    const id = requestAnimationFrame(() => {
      const main = document.getElementById('main-content');
      if (!main) return;
      const target = main.querySelector('h1, h2, [data-focus-initial]');
      if (target) {
        target.setAttribute('tabIndex', '-1');
        target.focus({ preventScroll:false });
      }
    });
    return () => cancelAnimationFrame(id);
  });
  return children;
}
