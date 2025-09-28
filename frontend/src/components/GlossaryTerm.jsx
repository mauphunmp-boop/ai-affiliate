import React from 'react';
import { Tooltip, Box } from '@mui/material';

// Central glossary map – extendable. Keys lowercase.
export const GLOSSARY = {
  shortlink: 'Link rút gọn nội bộ chuyển hướng qua hệ thống để ghi nhận clicks & tracking',
  template: 'Mẫu cấu hình chuyển đổi affiliate (chứa placeholders và default params)',
  platform: 'Nền tảng thương mại (vd: shopee, lazada...) dùng để chọn template phù hợp',
  offer: 'Sản phẩm / chiến dịch affiliate có thể quảng bá',
  merchant: 'Đối tác / nhà bán hàng tham gia chương trình affiliate',
  campaign: 'Một chiến dịch quảng bá với điều kiện và thời gian cụ thể',
  commission: 'Khoản hoa hồng nhận được khi đơn hàng thỏa điều kiện',
  conversion: 'Sự kiện chuyển đổi (đơn hàng hợp lệ) ghi nhận để tính hoa hồng',
};

export default function GlossaryTerm({ term, children, underline=true }) {
  const key = (term||'').toLowerCase();
  const label = GLOSSARY[key] || term;
  return (
    <Tooltip title={label} arrow enterDelay={300}>
      <Box component="span" sx={underline? { borderBottom:'1px dotted', cursor:'help' }: { cursor:'help' }} data-glossary-term={key}>
        {children || term}
      </Box>
    </Tooltip>
  );
}

export function glossaryExplain(term) { return GLOSSARY[(term||'').toLowerCase()]; }

// autoHighlight(content: string, terms?: string[]) -> React nodes with GlossaryTerm wrapping matched words.
// Simple word boundary regex; avoids nesting if already inside a tag by requiring plain string input.
export function autoHighlight(text, terms) {
  if (!text || typeof text !== 'string') return text;
  const keys = (terms && terms.length ? terms : Object.keys(GLOSSARY)).sort((a,b)=>b.length-a.length); // longer first
  const pattern = new RegExp(`\\b(${keys.map(k=>escapeReg(k)).join('|')})s?\\b`, 'gi');
  const parts = [];
  let lastIndex = 0; let m; let idx=0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > lastIndex) parts.push(text.slice(lastIndex, m.index));
    const raw = m[0];
    const base = raw.toLowerCase().replace(/s$/,'');
    parts.push(<GlossaryTerm key={`g-${idx++}`} term={base}>{raw}</GlossaryTerm>);
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function escapeReg(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
