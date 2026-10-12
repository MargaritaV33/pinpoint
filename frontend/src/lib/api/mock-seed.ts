import facade from "@/assets/render-facade.jpg";
import living from "@/assets/render-living.jpg";
import atrium from "@/assets/render-atrium.jpg";
import type { Comment, RenderImage, StudioUser } from "./types";
import type { DbPin, DbRoom, MockDb } from "./mock";

export const DEMO_EMAIL = "demo@pinpoint.studio";
export const DEMO_PASSWORD = "pinpoint";

export function createSeed(): MockDb {
  const user: StudioUser & { password: string } = {
    id: "u_demo",
    email: DEMO_EMAIL,
    name: "Studio Halden",
    password: DEMO_PASSWORD,
  };
  const rooms: DbRoom[] = [
    {
      id: "r_lakeside",
      ownerId: user.id,
      title: "Lakeside Villa — Round 2",
      clientName: "Marta Lind",
      createdAt: "2026-10-05T09:12:00.000Z",
      status: "open",
      guestToken: "lakeside-demo",
      approvedAt: null,
      approvedBy: null,
    },
    {
      id: "r_atrium",
      ownerId: user.id,
      title: "Harbour Office Atrium",
      clientName: "Nordvik Properties",
      createdAt: "2026-09-21T14:30:00.000Z",
      status: "approved",
      guestToken: "atrium-demo",
      approvedAt: "2026-09-28T10:00:00.000Z",
      approvedBy: "Jonas Berg",
    },
  ];
  const images: RenderImage[] = [
    { id: "i_facade", roomId: "r_lakeside", title: "Lake facade, golden hour", url: facade, superseded: false, createdAt: "2026-10-05T09:15:00.000Z" },
    { id: "i_living", roomId: "r_lakeside", title: "Living room", url: living, superseded: false, createdAt: "2026-10-05T09:16:00.000Z" },
    { id: "i_atrium", roomId: "r_atrium", title: "Atrium, ground level", url: atrium, superseded: false, createdAt: "2026-09-21T14:35:00.000Z" },
  ];
  const pins: DbPin[] = [
    { id: "p1", imageId: "i_facade", number: 1, x: 62.5, y: 30.2, type: "fix", status: "open", createdAt: "2026-10-06T08:01:00.000Z" },
    { id: "p2", imageId: "i_facade", number: 2, x: 25.4, y: 63.8, type: "question", status: "open", createdAt: "2026-10-06T08:05:00.000Z" },
    { id: "p3", imageId: "i_facade", number: 3, x: 84.1, y: 58.9, type: "like", status: null, createdAt: "2026-10-06T08:09:00.000Z" },
    { id: "p4", imageId: "i_living", number: 1, x: 70.2, y: 63.1, type: "fix", status: "resolved", createdAt: "2026-10-06T08:20:00.000Z" },
    { id: "p5", imageId: "i_living", number: 2, x: 44.0, y: 40.5, type: "like", status: null, createdAt: "2026-10-06T08:22:00.000Z" },
    { id: "p6", imageId: "i_atrium", number: 1, x: 55.0, y: 22.0, type: "like", status: null, createdAt: "2026-09-24T11:00:00.000Z" },
    { id: "p7", imageId: "i_atrium", number: 2, x: 30.0, y: 70.0, type: "fix", status: "resolved", createdAt: "2026-09-24T11:04:00.000Z" },
  ];
  const c = (id: string, pinId: string, text: string, authorName: string, authorRole: Comment["authorRole"], createdAt: string): Comment => ({
    id, pinId, text, authorName, authorRole, createdAt,
  });
  const comments: Comment[] = [
    c("c1", "p1", "Could the cladding on the upper floor be a shade darker? It reads too orange here.", "Marta Lind", "client", "2026-10-06T08:01:00.000Z"),
    c("c2", "p1", "Noted — we'll test a smoked oak finish in the next round.", "Studio Halden", "studio", "2026-10-06T09:30:00.000Z"),
    c("c3", "p2", "Is the jetty part of the scope, or just staging?", "Marta Lind", "client", "2026-10-06T08:05:00.000Z"),
    c("c4", "p3", "Love the outdoor fireplace and the reflections.", "Marta Lind", "client", "2026-10-06T08:09:00.000Z"),
    c("c5", "p4", "Please remove the throw from the sofa.", "Marta Lind", "client", "2026-10-06T08:20:00.000Z"),
    c("c6", "p4", "Done in the updated render.", "Studio Halden", "studio", "2026-10-07T10:00:00.000Z"),
    c("c7", "p5", "This view is exactly what we hoped for.", "Marta Lind", "client", "2026-10-06T08:22:00.000Z"),
    c("c8", "p6", "The timber roof is stunning.", "Jonas Berg", "client", "2026-09-24T11:00:00.000Z"),
    c("c9", "p7", "Add more planting along the left balustrade.", "Jonas Berg", "client", "2026-09-24T11:04:00.000Z"),
  ];
  return { users: [user], sessions: {}, rooms, images, pins, comments };
}
