import React from 'react';
import { Box, Paper, Stepper, Step, StepLabel, Button, Typography } from '@mui/material';
import { useT } from '../../i18n/I18nProvider.jsx';

const steps = ['source', 'mapping', 'confirm'];

export default function IngestWizard() {
  const { t } = useT();
  const [active, setActive] = React.useState(0);
  const [source, setSource] = React.useState({ type:'accesstrade', merchant:'' });
  const [mapping, setMapping] = React.useState({});
  const next = () => setActive(a => Math.min(a+1, steps.length-1));
  const prev = () => setActive(a => Math.max(a-1, 0));

  return (
    <Box>
      <Typography variant="h5" gutterBottom data-focus-initial>{t('ingest_wizard_title') || 'Ingest Wizard'}</Typography>
      <Paper sx={{ p:2 }}>
        <Stepper activeStep={active} alternativeLabel sx={{ mb:3 }}>
          {steps.map(s => <Step key={s}><StepLabel>{t(`ingest_step_${s}`) || s}</StepLabel></Step>)}
        </Stepper>
        {active===0 && <StepSource value={source} onChange={setSource} />}
        {active===1 && <StepMapping value={mapping} onChange={setMapping} />}
        {active===2 && <StepConfirm source={source} mapping={mapping} />}
        <Box sx={{ mt:3, display:'flex', gap:1 }}>
          <Button size="small" disabled={active===0} onClick={prev}>{t('back') || 'Quay lại'}</Button>
          {active < steps.length-1 && <Button size="small" variant="contained" onClick={next}>{t('next') || 'Tiếp'}</Button>}
          {active === steps.length-1 && <Button size="small" variant="contained" color="success" disabled>{t('finish') || 'Hoàn tất (stub)'}</Button>}
        </Box>
      </Paper>
    </Box>
  );
}

function StepSource() {
  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>Nguồn dữ liệu</Typography>
      <Typography variant="body2" color="text.secondary">(Stub) Chọn merchant / network cần ingest.</Typography>
    </Box>
  );
}
function StepMapping() {
  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>Mapping trường</Typography>
      <Typography variant="body2" color="text.secondary">(Stub) Cấu hình ánh xạ cột -&gt; thuộc tính chuẩn.</Typography>
    </Box>
  );
}
function StepConfirm({ source, mapping }) {
  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>Xác nhận</Typography>
      <Typography variant="body2" color="text.secondary">(Stub) Kiểm tra lại thông tin trước khi gửi ingest job.</Typography>
      <pre style={{ fontSize:11, background:'#f5f5f5', padding:8 }}>{JSON.stringify({ source, mapping }, null, 2)}</pre>
    </Box>
  );
}
