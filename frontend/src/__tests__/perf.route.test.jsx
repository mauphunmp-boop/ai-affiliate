import React from 'react';
import { render } from '@testing-library/react';
import { useRoutePerf } from '../hooks/useRoutePerf.js';

function Sample(){ useRoutePerf('SamplePage'); return <div>Hi</div>; }

describe('useRoutePerf global buffer', () => {
  it('pushes metric to window buffer', () => {
    render(<Sample />);
    // micro delay simulation not needed; metric pushed in effect
    expect((window.__routePerfMetrics||[]).some(m=>m.name==='SamplePage')).toBe(true);
  });
});
