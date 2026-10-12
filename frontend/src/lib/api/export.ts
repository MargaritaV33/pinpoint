import type { RoomDetail } from "./types";

/** Plain-text list of open pins, grouped by image. Pure. */
export function formatOpenPinsExport(detail: RoomDetail, exportedAt: Date = new Date()): string {
  const { room, images, pins } = detail;
  const lines: string[] = [
    `Pinpoint — open pins`,
    `Room: ${room.title}`,
    `Client: ${room.clientName}`,
    `Exported: ${exportedAt.toISOString().slice(0, 16).replace("T", " ")}`,
    "",
  ];
  let total = 0;
  for (const image of images) {
    const open = pins
      .filter((p) => p.imageId === image.id && p.status === "open")
      .sort((a, b) => a.number - b.number);
    if (open.length === 0) continue;
    lines.push(`== ${image.title}${image.superseded ? " (superseded)" : ""} ==`);
    for (const pin of open) {
      const first = pin.comments[0];
      const replies = pin.comments.length - 1;
      lines.push(
        `#${pin.number} [${pin.type}] ${first ? first.text : "(no comment)"}` +
          (first ? ` — ${first.authorName}` : "") +
          (replies > 0 ? ` (${replies} ${replies === 1 ? "reply" : "replies"})` : ""),
      );
      total++;
    }
    lines.push("");
  }
  if (total === 0) lines.push("No open pins.");
  return lines.join("\n").trimEnd() + "\n";
}
