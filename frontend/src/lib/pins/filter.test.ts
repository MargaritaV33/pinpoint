import { describe, expect, it } from "vitest";
import { countOpenPins, filterPins, getSessionFilter, isOpenPin, openPinCountsByImage, setSessionFilter } from "./filter";
import type { PinStatus, PinType } from "@/lib/api/types";

const p = (id: string, imageId: string, type: PinType, status: PinStatus) => ({ id, imageId, type, status });
const pins = [
  p("1", "a", "fix", "open"),
  p("2", "a", "question", "open"),
  p("3", "a", "fix", "resolved"),
  p("4", "a", "like", null),
  p("5", "b", "question", "resolved"),
  p("6", "b", "fix", "open"),
];

describe("pin filter", () => {
  it("all returns everything", () => expect(filterPins(pins, "all")).toHaveLength(6));
  it("open = fix/question with status open", () =>
    expect(filterPins(pins, "open").map((x) => x.id)).toEqual(["1", "2", "6"]));
  it("filters by type", () => {
    expect(filterPins(pins, "fix").map((x) => x.id)).toEqual(["1", "3", "6"]);
    expect(filterPins(pins, "question").map((x) => x.id)).toEqual(["2", "5"]);
    expect(filterPins(pins, "like").map((x) => x.id)).toEqual(["4"]);
  });
  it("likes are never open", () => expect(isOpenPin({ type: "like", status: "open" })).toBe(false));
});

describe("open pin counts", () => {
  it("counts per image", () => {
    expect(countOpenPins(pins, "a")).toBe(2);
    expect(countOpenPins(pins, "b")).toBe(1);
    expect(countOpenPins(pins, "z")).toBe(0);
  });
  it("builds a map omitting zero images", () =>
    expect(openPinCountsByImage([...pins, p("7", "c", "fix", "resolved")])).toEqual({ a: 2, b: 1 }));
});

describe("session filter memory", () => {
  it("defaults to all and remembers per room", () => {
    expect(getSessionFilter("r1")).toBe("all");
    setSessionFilter("r1", "fix");
    expect(getSessionFilter("r1")).toBe("fix");
    expect(getSessionFilter("r2")).toBe("all");
  });
});
