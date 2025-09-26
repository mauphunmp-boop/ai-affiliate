import React from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { if (this.props.onError) this.props.onError(error, info); }
  reset = () => { this.setState({ error: null }); };
  render() {
    if (this.state.error) {
      return (
        <Paper sx={{ p:3, m:2, border:'1px solid', borderColor:'error.main' }}>
          <Typography variant="h6" color="error" gutterBottom>Sự cố không mong muốn</Typography>
          <Typography variant="body2" sx={{ whiteSpace:'pre-wrap', mb:2 }}>{String(this.state.error.message || this.state.error)}</Typography>
          {process.env.NODE_ENV !== 'production' && (
            <Box sx={{ mb:2 }}>
              <Typography variant="caption" color="text.secondary">Stack (dev only):</Typography>
              <Typography variant="caption" component="pre" sx={{ maxHeight:160, overflow:'auto', p:1, bgcolor:'background.default', border:'1px solid', borderColor:'divider' }}>{this.state.error.stack}</Typography>
            </Box>
          )}
          <Button variant="contained" onClick={this.reset}>Thử tải lại khu vực</Button>
          <Button sx={{ ml:1 }} onClick={()=>window.location.reload()}>Tải lại trang</Button>
        </Paper>
      );
    }
    return this.props.children;
  }
}
