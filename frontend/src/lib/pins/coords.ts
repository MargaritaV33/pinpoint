// Pure pin coordinate math. Pins are stored as percentages (0–100) of the
// rendered image box so they stay put when the image is resized.

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface PercentPoint {
  x: number;
  y: number;
}

export const clamp = (v: number, min = 0, max = 100) => Math.min(max, Math.max(min, v));

const round = (v: number, decimals = 3) => {
  const f = 10 ** decimals;
  return Math.round(v * f) / f;
};

/** Client (viewport) coordinates → percent of the box. Null when outside or box is empty. */
export function clientToPercent(clientX: number, clientY: number, box: Box): PercentPoint | null {
  if (box.width <= 0 || box.height <= 0) return null;
  const rx = clientX - box.left;
  const ry = clientY - box.top;
  if (rx < 0 || ry < 0 || rx > box.width || ry > box.height) return null;
  return { x: round(clamp((rx / box.width) * 100)), y: round(clamp((ry / box.height) * 100)) };
}

/** Percent → pixel offset inside a box of the given size. */
export function percentToPixels(point: PercentPoint, size: { width: number; height: number }) {
  return { left: (clamp(point.x) / 100) * size.width, top: (clamp(point.y) / 100) * size.height };
}

/** CSS position for an absolutely-positioned marker. */
export function percentToStyle(point: PercentPoint): { left: string; top: string } {
  return { left: `${clamp(point.x)}%`, top: `${clamp(point.y)}%` };
}
