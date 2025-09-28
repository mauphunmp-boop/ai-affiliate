import React from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
// Correct hook name (provider exports useT)
import { useT } from '../i18n/I18nProvider.jsx';

// Named export (remove default here to avoid multiple default export error)
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { if (this.props.onError) this.props.onError(error, info); }
  componentDidUpdate(prevProps) {
    if (this.props.testError && this.props.testError !== prevProps.testError && !this.state.error) {
      this.setState({ error: new Error(this.props.testError) });
    }
  }
  reset = () => { this.setState({ error: null }); };
  render() {
    // Hook không dùng được trong class, nên wrap component bằng function HOC phía dưới.
    const activeError = this.state.error;
    if (activeError) {
      return (
        <Paper sx={{ p:3, m:2, border:'1px solid', borderColor:'error.main' }}>
          <Typography variant="h6" color="error" gutterBottom>{this.props.t('error_boundary_unexpected') || 'Sự cố không mong muốn'}</Typography>
          <Typography variant="body2" sx={{ whiteSpace:'pre-wrap', mb:2 }}>{String(activeError.message || activeError)}</Typography>
          {process.env.NODE_ENV !== 'production' && (
            <Box sx={{ mb:2 }}>
              <Typography variant="caption" color="text.secondary">Stack (dev only):</Typography>
              <Typography variant="caption" component="pre" sx={{ maxHeight:160, overflow:'auto', p:1, bgcolor:'background.default', border:'1px solid', borderColor:'divider' }}>{activeError.stack}</Typography>
            </Box>
          )}
          <Button variant="contained" onClick={this.reset}>{this.props.t('common_reload_area')||'Thử tải lại khu vực'}</Button>
          <Button sx={{ ml:1 }} onClick={()=>window.location.reload()}>{this.props.t('common_reload_page')||'Tải lại trang'}</Button>
        </Paper>
      );
    }
    return this.props.children;
  }
}

// Wrapper HOC to inject translation function into the class component.
// This is now the single default export.
export default function ErrorBoundaryWithI18n(props) {
  const { t } = useT();
  return <ErrorBoundary {...props} t={t} />;
}
