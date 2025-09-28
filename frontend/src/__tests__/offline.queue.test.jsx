import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { useOfflineQueue } from '../hooks/useOfflineQueue.js';

describe('useOfflineQueue', () => {
  it('enqueues and flushes actions', async () => {
    const exec = vi.fn().mockResolvedValue({ ok:true });
    const { result } = renderHook(()=> useOfflineQueue(exec));
    act(()=>{ result.current.enqueue('POST','/api/test',{a:1}); });
    expect(result.current.pending.length).toBe(1);
    await act(async ()=> { await result.current.flush(); });
    expect(exec).toHaveBeenCalled();
    expect(result.current.pending.length).toBe(0);
  });
});
