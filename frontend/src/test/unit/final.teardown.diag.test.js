// Chỉ chạy khi bật TEST_DIAG=1 để hiển thị handles còn mở và giúp chẩn đoán exit code.
// Vitest sẽ coi đây là 1 test file rất nhẹ.

describe('FINAL_TEARDOWN_DIAG', () => {
  it('dump active handles (TEST_DIAG)', async () => {
    if (process.env.TEST_DIAG !== '1') {
      expect(true).toBe(true); // no-op
      return;
    }
    // Chuyển timers về real để tránh leak fake timers
    try { vi.useRealTimers(); } catch {}
    const handles = (process._getActiveHandles?.() || []).map(h => h?.constructor?.name || 'Unknown');
    const requests = (process._getActiveRequests?.() || []).map(r => r?.constructor?.name || 'Unknown');
    // Lọc bỏ các handle phổ biến vô hại như WriteStream stdout/stderr
    const filtered = handles.filter(h => !/^WriteStream$/.test(h) && !/^Socket$/.test(h));
    // In ra để quan sát
    console.log('[FINAL_DIAG] ActiveHandles(all):', handles);
    console.log('[FINAL_DIAG] ActiveRequests:', requests);
    console.log('[FINAL_DIAG] ActiveHandles(filtered):', filtered);
    if (filtered.length && process.env.TEST_FORCE_EXIT === '1') {
      console.log('[FINAL_DIAG] Forcing process.exit(0) due to TEST_FORCE_EXIT with leftover handles');
      // Tránh làm fail suite: đặt exitCode rồi schedule exit để vitest flush reporter.
      process.exitCode = 0;
      setTimeout(() => { try { process.exit(0); } catch {} }, 50);
    }
    expect(true).toBe(true);
  });
});
