import assert from 'node:assert/strict';
import {
  createSignalRingGrid,
  renderSignalRingRows,
  rowsToPlainText
} from './signal-ring.js';

const colorRows = renderSignalRingRows({color: true, grid: createSignalRingGrid()});
const colorText = rowsToPlainText(colorRows);

assert.ok(colorRows.length >= 10, 'half-block logo should be vertically compact but visible');
assert.ok(colorRows.some(row => row.some(span => span.char === '\u2580')), 'colored logo should use upper half-blocks');
assert.ok(colorRows.some(row => row.some(span => span.char === '\u2584')), 'colored logo should use lower half-block edge pixels');
assert.ok(
  colorRows.some(row => row.some(span => span.char === '\u2580' && span.fg && span.bg)),
  'colored logo should combine top and bottom pixel colors in one terminal cell'
);
assert.ok(!colorText.includes('\u2588\u2588'), 'half-block logo should not use old full-block cells');
assert.ok(!colorText.includes('##'), 'half-block logo should not use old hash fallback cells');

const plainRows = renderSignalRingRows({color: false, grid: createSignalRingGrid()});
const plainText = rowsToPlainText(plainRows);

assert.equal(plainText, '* Synapse Signal Ring');
assert.ok(!plainText.includes('\u001b['), 'plain fallback should not contain ANSI escape codes');
assert.ok(!plainText.includes('\u2588\u2588'), 'plain fallback should not use full blocks');
assert.ok(!plainText.includes('##'), 'plain fallback should not use hash blocks');

const missingRows = renderSignalRingRows({color: true, grid: null});
assert.equal(rowsToPlainText(missingRows), '* Synapse Signal Ring');
