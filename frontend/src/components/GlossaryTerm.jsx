import React from 'react';
import { Tooltip, Box } from '@mui/material';

const GLOSSARY = {
  shortlink: 'Link rút gọn nội bộ chuyển hướng qua hệ thống để ghi nhận clicks & tracking',
  template: 'Mẫu cấu hình chuyển đổi affiliate (chứa placeholders và default params)',
  platform: 'Nền tảng thương mại (vd: shopee, lazada...) dùng để chọn template phù hợp',
  offer: 'Sản phẩm / chiến dịch affiliate có thể quảng bá',
};

export default function GlossaryTerm({ term, children, underline=true }) {
  const label = GLOSSARY[term] || term;
  return (
    <Tooltip title={label} arrow enterDelay={300}>
      <Box component="span" sx={underline? { borderBottom:'1px dotted', cursor:'help' }: { cursor:'help' }}>
        {children || term}
      </Box>
    </Tooltip>
  );
}

export function glossaryExplain(term) { return GLOSSARY[term]; }
