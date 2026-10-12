import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createHttpApi } from "./http";

const BASE = "http://localhost:8091";
const TOKEN_KEY = "pinpoint.token";

/** Minimal fetch Response stand-in — just what `req()` in http.ts reads. */
function makeResponse(status: number, body: unknown, contentType = "application/json"): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? contentType : null) },
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("http api: auth requests and token storage", () => {
  it("POSTs login as JSON to /auth/login and stores the returned token", async () => {
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      expect(url).toBe(`${BASE}/auth/login`);
      expect(init.method).toBe("POST");
      expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
      expect(JSON.parse(init.body as string)).toEqual({ email: "a@studio.test", password: "secret" });
      return makeResponse(200, { token: "tok-login", user: { id: "u1", email: "a@studio.test", name: "a" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await createHttpApi(BASE).login("a@studio.test", "secret");

    expect(session.token).toBe("tok-login");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-login");
  });

  it("POSTs signup as JSON to /auth/signup and stores the returned token", async () => {
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      expect(url).toBe(`${BASE}/auth/signup`);
      expect(init.method).toBe("POST");
      expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
      expect(JSON.parse(init.body as string)).toEqual({ email: "new@studio.test", password: "secret123" });
      return makeResponse(201, { token: "tok-signup", user: { id: "u2", email: "new@studio.test", name: "new" } });
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await createHttpApi(BASE).signup("new@studio.test", "secret123");

    expect(session.token).toBe("tok-signup");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("tok-signup");
  });

  it("sends Authorization: Bearer <token> when a token is stored, and omits it when none is stored", async () => {
    localStorage.setItem(TOKEN_KEY, "tok-present");
    const withToken = vi.fn(async (_url: string, init: RequestInit) => {
      expect((init.headers as Record<string, string>)["Authorization"]).toBe("Bearer tok-present");
      return makeResponse(200, []);
    });
    vi.stubGlobal("fetch", withToken);
    await createHttpApi(BASE).listRooms();
    expect(withToken).toHaveBeenCalledTimes(1);

    localStorage.removeItem(TOKEN_KEY);
    const withoutToken = vi.fn(async (_url: string, init: RequestInit) => {
      expect(init.headers).not.toHaveProperty("Authorization");
      return makeResponse(200, []);
    });
    vi.stubGlobal("fetch", withoutToken);
    await createHttpApi(BASE).listRooms();
    expect(withoutToken).toHaveBeenCalledTimes(1);
  });

  it("clears the stored token when a response is 401", async () => {
    localStorage.setItem(TOKEN_KEY, "stale-token");
    const fetchMock = vi.fn(async () => makeResponse(401, { detail: "Invalid or expired token." }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createHttpApi(BASE).listRooms()).rejects.toMatchObject({ status: 401 });

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});

describe("http api: uploadImage multipart shape", () => {
  it("sends a real FormData body with title and file fields, and sets no Content-Type itself", async () => {
    const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
      expect(url).toBe(`${BASE}/rooms/r1/images`);
      expect(init.method).toBe("POST");
      expect(init.body).toBeInstanceOf(FormData);
      const fd = init.body as FormData;
      expect(fd.get("title")).toBe("Kitchen");
      expect(fd.get("file")).toBeInstanceOf(File);
      expect((fd.get("file") as File).name).toBe("kitchen.png");
      expect(Array.from(fd.keys()).sort()).toEqual(["file", "title"]);
      // fetch/the browser must set the multipart boundary; req() must not.
      expect(init.headers).not.toHaveProperty("Content-Type");
      return makeResponse(201, {
        id: "i1",
        roomId: "r1",
        title: "Kitchen",
        url: "/rooms/r1/images/i1/file",
        superseded: false,
        createdAt: "2026-01-01T00:00:00Z",
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["bytes"], "kitchen.png", { type: "image/png" });
    const image = await createHttpApi(BASE).uploadImage("r1", { title: "Kitchen", file });

    expect(image.url).toBe(`${BASE}/rooms/r1/images/i1/file`);
  });
});

describe("http api: path building and URL-encoding", () => {
  it("encodes id path segments for id-taking methods", async () => {
    const calls: string[] = [];
    const fetchMock = vi.fn(async (url: string) => {
      calls.push(url);
      if (url.startsWith(`${BASE}/rooms/`)) {
        return makeResponse(200, {
          room: {
            id: "x",
            title: "T",
            clientName: "C",
            createdAt: "2026-01-01T00:00:00Z",
            status: "open",
            guestToken: "g",
            approvedAt: null,
            approvedBy: null,
          },
          images: [],
          pins: [],
        });
      }
      return makeResponse(200, {});
    });
    vi.stubGlobal("fetch", fetchMock);

    const api = createHttpApi(BASE);
    await api.getRoom("room with space/slash");
    await api.setPinStatus("pin#1", "resolved");
    await api.addGuestComment("token&weird", "pin/2", "hello", "Name");

    expect(calls[0]).toBe(`${BASE}/rooms/${encodeURIComponent("room with space/slash")}`);
    expect(calls[1]).toBe(`${BASE}/pins/${encodeURIComponent("pin#1")}`);
    expect(calls[2]).toBe(
      `${BASE}/guest/${encodeURIComponent("token&weird")}/pins/${encodeURIComponent("pin/2")}/comments`,
    );
  });
});

describe("http api: RenderImage.url rewrite to an absolute URL", () => {
  it("rewrites a relative RenderImage.url (direct, e.g. from uploadImage) using the configured base URL", async () => {
    const fetchMock = vi.fn(async () =>
      makeResponse(201, {
        id: "i1",
        roomId: "r1",
        title: "Kitchen",
        url: "/rooms/r1/images/i1/file",
        superseded: false,
        createdAt: "2026-01-01T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["bytes"], "k.png", { type: "image/png" });
    const image = await createHttpApi(BASE).uploadImage("r1", { title: "Kitchen", file });

    expect(image.url).toBe(`${BASE}/rooms/r1/images/i1/file`);
  });

  it("rewrites every image's url nested inside a RoomDetail (getRoom and getGuestRoom)", async () => {
    const roomDetail = {
      room: {
        id: "r1",
        title: "T",
        clientName: "C",
        createdAt: "2026-01-01T00:00:00Z",
        status: "open",
        guestToken: "g1",
        approvedAt: null,
        approvedBy: null,
      },
      images: [
        {
          id: "i1",
          roomId: "r1",
          title: "Kitchen",
          url: "/rooms/r1/images/i1/file",
          superseded: false,
          createdAt: "2026-01-01T00:00:00Z",
        },
        {
          id: "i2",
          roomId: "r1",
          title: "Already absolute",
          url: "https://cdn.example.test/i2/file",
          superseded: false,
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
      pins: [],
    };
    const fetchMock = vi.fn(async () => makeResponse(200, roomDetail));
    vi.stubGlobal("fetch", fetchMock);

    const api = createHttpApi(BASE);
    const detail = await api.getRoom("r1");
    expect(detail.images[0].url).toBe(`${BASE}/rooms/r1/images/i1/file`);
    // Already-absolute URLs are left untouched, not double-prefixed.
    expect(detail.images[1].url).toBe("https://cdn.example.test/i2/file");

    const guestDetail = await api.getGuestRoom("g1");
    expect(guestDetail.images[0].url).toBe(`${BASE}/rooms/r1/images/i1/file`);
  });
});
