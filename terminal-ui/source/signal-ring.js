export const SIGNAL_RING_PALETTE = {
  B: '#2f8cff',
  C: '#22bdf2',
  D: '#062d8f',
  L: '#6aa8ff',
  T: '#2cc3bd',
  V: '#5f5df2'
};

const WIDTH = 42;
const HEIGHT = 28;
const CENTER_X = (WIDTH - 1) / 2;
const CENTER_Y = (HEIGHT - 1) / 2;

const SIGNAL_SEGMENTS = [
  [-90, 6.8, 13.2, 'B'], [-80, 7.2, 12.4, 'C'], [-70, 7.1, 12.7, 'L'],
  [-60, 7.5, 11.6, 'V'], [-50, 7.2, 13.1, 'C'], [-40, 7.4, 12.2, 'B'],
  [-30, 7.0, 13.5, 'D'], [-20, 7.6, 11.8, 'L'], [-10, 7.3, 13.0, 'C'],
  [0, 7.0, 14.6, 'D'], [10, 7.4, 12.9, 'B'], [20, 7.2, 13.8, 'C'],
  [30, 7.6, 12.4, 'V'], [40, 7.1, 13.0, 'L'], [50, 7.5, 11.7, 'B'],
  [60, 7.0, 13.6, 'C'], [70, 7.7, 12.2, 'T'], [80, 7.1, 12.9, 'B'],
  [90, 6.9, 14.0, 'B'], [100, 7.4, 12.0, 'L'], [110, 7.2, 13.5, 'C'],
  [120, 7.6, 11.9, 'V'], [130, 7.0, 13.3, 'D'], [140, 7.5, 12.2, 'B'],
  [150, 7.1, 13.7, 'C'], [160, 7.6, 12.4, 'L'], [170, 7.3, 13.9, 'B'],
  [180, 7.0, 14.5, 'B'], [190, 7.4, 12.4, 'C'], [200, 7.1, 13.7, 'L'],
  [210, 7.5, 12.1, 'V'], [220, 7.0, 13.2, 'B'], [230, 7.6, 12.0, 'D'],
  [240, 7.2, 13.6, 'C'], [250, 7.7, 12.3, 'T'], [260, 7.0, 13.2, 'L']
];

export function createSignalRingGrid() {
  const grid = Array.from({length: HEIGHT}, () => Array.from({length: WIDTH}, () => '.'));

  for (const [degrees, innerRadius, outerRadius, token] of SIGNAL_SEGMENTS) {
    drawRadialSegment(grid, degrees, innerRadius, outerRadius, token);
  }

  return grid;
}

export function renderSignalRingRows({color = true, grid = createSignalRingGrid()} = {}) {
  if (!color || !isGrid(grid)) {
    return fallbackSignalRingRows();
  }

  const rows = [];
  for (let y = 0; y < grid.length; y += 2) {
    const topRow = grid[y] || [];
    const bottomRow = grid[y + 1] || [];
    const spans = [];
    const width = Math.max(topRow.length, bottomRow.length);

    for (let x = 0; x < width; x += 1) {
      const top = colorForToken(topRow[x]);
      const bottom = colorForToken(bottomRow[x]);
      spans.push(halfBlockSpan(top, bottom));
    }

    rows.push(spans);
  }

  return trimRows(rows);
}

export function fallbackSignalRingRows() {
  return [
    [{char: '* Synapse Signal Ring', fg: undefined, bg: undefined, fallback: true}]
  ];
}

export function rowsToPlainText(rows) {
  return rows.map(row => row.map(span => span.char).join('')).join('\n');
}

function drawRadialSegment(grid, degrees, innerRadius, outerRadius, token) {
  const start = polarPoint(degrees, innerRadius);
  const end = polarPoint(degrees, outerRadius);
  drawLine(grid, start.x, start.y, end.x, end.y, token);
}

function polarPoint(degrees, radius) {
  const radians = (degrees * Math.PI) / 180;
  return {
    x: Math.round(CENTER_X + Math.cos(radians) * radius),
    y: Math.round(CENTER_Y + Math.sin(radians) * radius)
  };
}

function drawLine(grid, x1, y1, x2, y2, token) {
  const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
  for (let index = 0; index <= steps; index += 1) {
    const t = steps === 0 ? 0 : index / steps;
    const x = Math.round(x1 + (x2 - x1) * t);
    const y = Math.round(y1 + (y2 - y1) * t);
    if (grid[y]?.[x] !== undefined) {
      grid[y][x] = token;
    }
  }
}

function halfBlockSpan(top, bottom) {
  if (!top && !bottom) {
    return {char: ' ', fg: undefined, bg: undefined};
  }
  if (top && bottom) {
    return {char: '\u2580', fg: top, bg: bottom};
  }
  if (top) {
    return {char: '\u2580', fg: top, bg: undefined};
  }
  return {char: '\u2584', fg: bottom, bg: undefined};
}

function colorForToken(token) {
  if (!token || token === '.') {
    return undefined;
  }
  return SIGNAL_RING_PALETTE[token] || SIGNAL_RING_PALETTE.B;
}

function isGrid(grid) {
  return Array.isArray(grid) && grid.length > 0 && grid.every(row => Array.isArray(row));
}

function trimRows(rows) {
  const nonEmptyRows = rows.filter(row => row.some(span => span.char !== ' '));
  if (nonEmptyRows.length === 0) {
    return fallbackSignalRingRows();
  }

  const firstUsedColumn = Math.min(...nonEmptyRows.map(firstNonSpaceIndex));
  const lastUsedColumn = Math.max(...nonEmptyRows.map(lastNonSpaceIndex));
  return nonEmptyRows.map(row => row.slice(firstUsedColumn, lastUsedColumn + 1));
}

function firstNonSpaceIndex(row) {
  const index = row.findIndex(span => span.char !== ' ');
  return index === -1 ? row.length : index;
}

function lastNonSpaceIndex(row) {
  for (let index = row.length - 1; index >= 0; index -= 1) {
    if (row[index].char !== ' ') {
      return index;
    }
  }
  return 0;
}
