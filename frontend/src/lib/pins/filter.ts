import type { Pin } from "@/lib/api/types";

export type PinFilter = "all" | "open" | "fix" | "question" | "like";

export const PIN_FILTERS: { value: PinFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "fix", label: "Fix" },
  { value: "question", label: "Question" },
  { value: "like", label: "Like" },
];

/** Open = actionable (fix/question) pin with status "open". */
export function isOpenPin(pin: Pick<Pin, "type" | "status">): boolean {
  return (pin.type === "fix" || pin.type === "question") && pin.status === "open";
}

export function matchesFilter(pin: Pick<Pin, "type" | "status">, filter: PinFilter): boolean {
  if (filter === "all") return true;
  if (filter === "open") return isOpenPin(pin);
  return pin.type === filter;
}

export function filterPins<T extends Pick<Pin, "type" | "status">>(pins: T[], filter: PinFilter): T[] {
  return filter === "all" ? pins : pins.filter((p) => matchesFilter(p, filter));
}

export function countOpenPins(pins: Pick<Pin, "imageId" | "type" | "status">[], imageId: string): number {
  return pins.filter((p) => p.imageId === imageId && isOpenPin(p)).length;
}

export function openPinCountsByImage(pins: Pick<Pin, "imageId" | "type" | "status">[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const p of pins) if (isOpenPin(p)) out[p.imageId] = (out[p.imageId] ?? 0) + 1;
  return out;
}

/** Per-session (in-memory) filter choice, keyed by room. */
const sessionFilters = new Map<string, PinFilter>();
export const getSessionFilter = (roomId: string): PinFilter => sessionFilters.get(roomId) ?? "all";
export const setSessionFilter = (roomId: string, f: PinFilter) => void sessionFilters.set(roomId, f);
