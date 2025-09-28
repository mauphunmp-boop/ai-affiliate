import { describe, test, expect } from 'vitest';
import { parseJsonWithLineInfo, buildJsonErrorSnippet } from '../../utils/jsonPosition.js';

describe('jsonPosition utilities', () => {
  test('success parse', () => {
    const res = parseJsonWithLineInfo('{"a":1}');
    expect(res.error).toBeUndefined();
    expect(res.value).toEqual({ a:1 });
  });
  test('empty string -> undefined value', () => {
    const res = parseJsonWithLineInfo('   ');
    expect(res.value).toBeUndefined();
  });
  test('error line/column detection', () => {
    const input = '{\n  "a": 1,\n  "b": ,\n  "c":3\n}';
    const res = parseJsonWithLineInfo(input);
    expect(res.error).toBeDefined();
  // line / column should be numeric when position extracted
  expect(typeof res.error.line).toBe('number');
  expect(typeof res.error.column).toBe('number');
  expect(res.error.line).toBeGreaterThan(0);
  expect(res.error.column).toBeGreaterThan(0);
    const snippet = buildJsonErrorSnippet(input, res.error.position);
    expect(snippet).toContain('^');
  });
});
