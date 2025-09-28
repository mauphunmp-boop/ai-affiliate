import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { useRoutePerf } from '../hooks/useRoutePerf.js';

describe('useRoutePerf', () => {
  it('gọi callback với metric hợp lệ', () => {
    const metrics = [];
    const cb = (m) => metrics.push(m);
  renderHook(({ n }) => useRoutePerf(n, cb), { initialProps: { n: 'TestPage' } });
    // flush layout effect
    act(()=>{});
    expect(metrics.length).toBe(1);
    expect(metrics[0].name).toBe('TestPage');
    expect(typeof metrics[0].duration).toBe('number');
    expect(metrics[0].duration).toBeGreaterThanOrEqual(0); // very small in jsdom
  });
});
