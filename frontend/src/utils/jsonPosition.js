// Parse JSON and derive line/column from SyntaxError position (V8-style).
// Returns { value } on success (value can be undefined for empty), or { error: { message, position, line, column } }.
export function parseJsonWithLineInfo(text) {
  const original = text;
  if (typeof text !== 'string') return { error: { message: 'Input must be string' } };
  const trimmed = text.trim();
  if (!trimmed) return { value: undefined };
  try {
    const value = JSON.parse(text);
    return { value };
  } catch (e) {
    const msg = e?.message || 'Invalid JSON';
    const match = msg.match(/position (\d+)/i);
    let position = null;
    if (match) position = parseInt(match[1], 10);
    let line = null, column = null;
    if (position != null) {
      line = 1; column = 1;
      for (let i = 0; i < original.length && i < position; i++) {
        if (original[i] === '\n') { line++; column = 1; } else { column++; }
      }
    }
    return { error: { message: msg, position, line, column } };
  }
}

export function buildJsonErrorSnippet(text, position, radius = 30) {
  if (position == null) return null;
  const start = Math.max(0, position - radius);
  const end = Math.min(text.length, position + radius);
  const segment = text.slice(start, end);
  const caretIdx = position - start;
  const caret = ' '.repeat(Math.max(0, caretIdx)) + '^';
  return segment + '\n' + caret;
}
