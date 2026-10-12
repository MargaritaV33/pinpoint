import { describe, expect, it } from "vitest";
import { clamp, clientToPercent, percentToPixels, percentToStyle } from "./coords";

const box = { left: 100, top: 50, width: 800, height: 400 };

describe("pin coordinates", () => {
  it("maps a click to percentages of the image box", () => {
    expect(clientToPercent(500, 250, box)).toEqual({ x: 50, y: 50 });
    expect(clientToPercent(100, 50, box)).toEqual({ x: 0, y: 0 });
    expect(clientToPercent(900, 450, box)).toEqual({ x: 100, y: 100 });
  });

  it("returns null outside the box or for an empty box", () => {
    expect(clientToPercent(99, 60, box)).toBeNull();
    expect(clientToPercent(200, 451, box)).toBeNull();
    expect(clientToPercent(0, 0, { left: 0, top: 0, width: 0, height: 10 })).toBeNull();
  });

  it("rounds to 3 decimals", () => {
    expect(clientToPercent(100 + 800 / 3, 50, box)).toEqual({ x: 33.333, y: 0 });
  });

  it("is resize-independent (round-trips through different sizes)", () => {
    const p = clientToPercent(340, 150, box)!; // 30%, 25%
    expect(p).toEqual({ x: 30, y: 25 });
    expect(percentToPixels(p, { width: 800, height: 400 })).toEqual({ left: 240, top: 100 });
    expect(percentToPixels(p, { width: 1600, height: 800 })).toEqual({ left: 480, top: 200 });
  });

  it("produces clamped CSS percentages", () => {
    expect(percentToStyle({ x: 12.5, y: 80 })).toEqual({ left: "12.5%", top: "80%" });
    expect(percentToStyle({ x: -5, y: 140 })).toEqual({ left: "0%", top: "100%" });
    expect(clamp(50)).toBe(50);
  });
});
