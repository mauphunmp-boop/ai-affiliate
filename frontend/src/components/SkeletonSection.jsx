import React from 'react';
import { Stack, Skeleton, Box } from '@mui/material';

/**
 * SkeletonSection
 * Reusable loading placeholder.
 * Props:
 *  - variant: 'table' | 'cards' | 'detail'
 *  - rows: number (for table/cards) default 5
 *  - cardsPerRow: number (for cards) default 2
 *  - height: row height approximation
 */
export default function SkeletonSection({ variant='table', rows=5, cardsPerRow=2, height=48 }) {
  if (variant === 'cards') {
    const arr = Array.from({ length: rows * cardsPerRow });
    return (
      <Box sx={{ display:'grid', gridTemplateColumns:{ xs:'repeat(auto-fill,minmax(140px,1fr))', sm:`repeat(${cardsPerRow},1fr)` }, gap:1 }}>
        {arr.map((_,i)=> (
          <Stack key={i} spacing={0.5} sx={{ p:1, border:'1px solid', borderColor:'divider', borderRadius:1 }}>
            <Skeleton variant="rectangular" height={80} />
            <Skeleton width="80%" />
            <Skeleton width="60%" />
          </Stack>
        ))}
      </Box>
    );
  }
  if (variant === 'detail') {
    return (
      <Stack spacing={1}>
        <Skeleton width={160} />
        <Skeleton width={240} />
        <Skeleton variant="rectangular" height={120} />
        <Skeleton width="50%" />
        <Skeleton width="30%" />
      </Stack>
    );
  }
  // table default
  return (
    <Stack spacing={0.6}>
      {Array.from({ length: rows }).map((_,i)=> (
        <Skeleton key={i} variant="rectangular" height={height} />
      ))}
    </Stack>
  );
}
