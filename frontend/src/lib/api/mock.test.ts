import { beforeEach, describe, expect, it } from "vitest";
import type { ApiClient } from "./client";
import { createMemoryStorage, createMockApi, type KeyValueStorage } from "./mock";
import { DEMO_EMAIL, DEMO_PASSWORD } from "./mock-seed";
import { ApiError } from "./types";
import { formatOpenPinsExport } from "./export";

let storage: KeyValueStorage;
let api: ApiClient;

beforeEach(() => {
  storage = createMemoryStorage();
  api = createMockApi({ storage: () => storage });
});

const login = () => api.login(DEMO_EMAIL, DEMO_PASSWORD);

describe("mock api: auth", () => {
  it("rejects wrong credentials and accepts the demo user", async () => {
    await expect(api.login(DEMO_EMAIL, "nope")).rejects.toMatchObject({ status: 401 });
    const s = await login();
    expect(s.user.email).toBe(DEMO_EMAIL);
    expect(await api.getCurrentUser()).toMatchObject({ email: DEMO_EMAIL });
    await api.logout();
    expect(await api.getCurrentUser()).toBeNull();
  });

  it("requires auth for studio calls", async () => {
    await expect(api.listRooms()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("mock api: rooms", () => {
  it("lists seeded rooms with open pin counts", async () => {
    await login();
    const rooms = await api.listRooms();
    expect(rooms).toHaveLength(2);
    const lake = rooms.find((r) => r.id === "r_lakeside")!;
    expect(lake.openPinCount).toBe(2);
  });

  it("creates a room with a guest token", async () => {
    await login();
    const room = await api.createRoom({ title: "New", clientName: "ACME" });
    expect(room.status).toBe("open");
    expect(room.guestToken).toBeTruthy();
    expect((await api.getGuestRoom(room.guestToken)).room.id).toBe(room.id);
  });

  it("validates uploads", async () => {
    await login();
    const gif = new File(["x"], "a.gif", { type: "image/gif" });
    await expect(api.uploadImage("r_lakeside", { title: "x", file: gif })).rejects.toMatchObject({ status: 400 });
    const big = new File(["x"], "a.png", { type: "image/png" });
    Object.defineProperty(big, "size", { value: 16 * 1024 * 1024 });
    await expect(api.uploadImage("r_lakeside", { title: "x", file: big })).rejects.toMatchObject({ status: 400 });
    const ok = new File(["png"], "ok.png", { type: "image/png" });
    const img = await api.uploadImage("r_lakeside", { title: "Kitchen", file: ok });
    expect(img.url.startsWith("data:image/png")).toBe(true);
  });
});

describe("mock api: pins and threads", () => {
  it("creates sequential pins per image with a first comment", async () => {
    const pin = await api.createGuestPin("lakeside-demo", {
      imageId: "i_facade", x: 10, y: 20, type: "fix", text: "Darker roof", authorName: "Marta",
    });
    expect(pin.number).toBe(4);
    expect(pin.status).toBe("open");
    expect(pin.comments[0]).toMatchObject({ text: "Darker roof", authorRole: "client" });
    const like = await api.createGuestPin("lakeside-demo", {
      imageId: "i_living", x: 1, y: 1, type: "like", text: "Nice", authorName: "Marta",
    });
    expect(like.number).toBe(3);
    expect(like.status).toBeNull();
  });

  it("lets studio resolve/reopen but not on like pins", async () => {
    await login();
    expect((await api.setPinStatus("p1", "resolved")).status).toBe("resolved");
    expect((await api.setPinStatus("p1", "open")).status).toBe("open");
    await expect(api.setPinStatus("p3", "resolved")).rejects.toMatchObject({ status: 400 });
  });

  it("threads replies from both roles", async () => {
    await login();
    await api.addStudioComment("p2", "Staging only.");
    await api.addGuestComment("lakeside-demo", "p2", "Thanks!", "Marta");
    const { pins } = await api.getRoom("r_lakeside");
    const roles = pins.find((p) => p.id === "p2")!.comments.map((c) => c.authorRole);
    expect(roles).toEqual(["client", "studio", "client"]);
  });

  it("blocks pins on superseded images but keeps them readable", async () => {
    await login();
    await api.setImageSuperseded("i_facade", true);
    await expect(
      api.createGuestPin("lakeside-demo", { imageId: "i_facade", x: 5, y: 5, type: "fix", text: "x", authorName: "M" }),
    ).rejects.toMatchObject({ status: 409 });
    const { pins } = await api.getGuestRoom("lakeside-demo");
    expect(pins.filter((p) => p.imageId === "i_facade")).toHaveLength(3);
  });

  it("approve and close", async () => {
    await login();
    expect((await api.approveRound("lakeside-demo", "Marta")).status).toBe("approved");
    await api.closeRoom("r_lakeside");
    await expect(api.addGuestComment("lakeside-demo", "p1", "hi", "M")).rejects.toMatchObject({ status: 403 });
    await expect(api.approveRound("lakeside-demo", "M")).rejects.toMatchObject({ status: 403 });
  });

  it("persists across client instances sharing storage", async () => {
    const other = createMockApi({ storage: () => storage });
    await api.addGuestComment("lakeside-demo", "p1", "From tab A", "M");
    const { pins } = await other.getGuestRoom("lakeside-demo");
    expect(pins.find((p) => p.id === "p1")!.comments.at(-1)!.text).toBe("From tab A");
  });
});

describe("export", () => {
  it("lists only open pins grouped by image", async () => {
    await login();
    const text = await api.exportOpenPins("r_lakeside");
    expect(text).toContain("== Lake facade, golden hour ==");
    expect(text).toContain("#1 [fix]");
    expect(text).toContain("#2 [question]");
    expect(text).not.toContain("Living room");
    expect(text).not.toContain("[like]");
  });

  it("says when nothing is open", () => {
    const out = formatOpenPinsExport({
      room: { id: "r", title: "T", clientName: "C", createdAt: "", status: "open", guestToken: "g", approvedAt: null, approvedBy: null },
      images: [],
      pins: [],
    });
    expect(out).toContain("No open pins.");
  });
});
