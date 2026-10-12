import type { ApiClient } from "./client";
import { ApiError, type RenderImage, type RoomDetail } from "./types";

const TOKEN_KEY = "pinpoint.token";

/**
 * The backend documents `RenderImage.url` as "the path to this image's
 * bytes" and returns it as a path relative to the backend's own origin
 * (e.g. `/rooms/{roomId}/images/{imageId}/file`), not the frontend's. An
 * `<img src>` resolves a relative URL against the *page's* origin, so it
 * must be rewritten to an absolute URL against this client's `baseUrl`.
 */
function withAbsoluteImageUrl(baseUrl: string, image: RenderImage): RenderImage {
  return image.url.startsWith("/") ? { ...image, url: `${baseUrl}${image.url}` } : image;
}

function withAbsoluteImageUrls(baseUrl: string, detail: RoomDetail): RoomDetail {
  return { ...detail, images: detail.images.map((image) => withAbsoluteImageUrl(baseUrl, image)) };
}

/** Real implementation against the future FastAPI service. */
export function createHttpApi(baseUrl: string): ApiClient {
  const token = () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY));

  async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    const t = token();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    let payload: BodyInit | null = null;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch(`${baseUrl}${path}`, { method, headers, body: payload });
    if (!res.ok) {
      if (res.status === 401 && typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
      let msg = res.statusText;
      try {
        msg = (await res.json()).detail ?? msg;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, String(msg));
    }
    if (res.status === 204) return undefined as T;
    const type = res.headers.get("content-type") ?? "";
    return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
  }
  const enc = encodeURIComponent;

  return {
    async signup(email, password) {
      const s = await req<Awaited<ReturnType<ApiClient["signup"]>>>("POST", "/auth/signup", { email, password });
      localStorage.setItem(TOKEN_KEY, s.token);
      return s;
    },
    async login(email, password) {
      const s = await req<Awaited<ReturnType<ApiClient["login"]>>>("POST", "/auth/login", { email, password });
      localStorage.setItem(TOKEN_KEY, s.token);
      return s;
    },
    async logout() {
      try {
        await req("POST", "/auth/logout");
      } finally {
        localStorage.removeItem(TOKEN_KEY);
      }
    },
    async getCurrentUser() {
      if (!token()) return null;
      try {
        return await req("GET", "/auth/me");
      } catch {
        return null;
      }
    },
    listRooms: () => req("GET", "/rooms"),
    createRoom: (input) => req("POST", "/rooms", input),
    getRoom: async (id) => withAbsoluteImageUrls(baseUrl, await req<RoomDetail>("GET", `/rooms/${enc(id)}`)),
    closeRoom: (id) => req("POST", `/rooms/${enc(id)}/close`),
    exportOpenPins: (id) => req("GET", `/rooms/${enc(id)}/export`),
    uploadImage: async (roomId, { title, file }) => {
      const fd = new FormData();
      fd.append("title", title);
      fd.append("file", file);
      return withAbsoluteImageUrl(baseUrl, await req<RenderImage>("POST", `/rooms/${enc(roomId)}/images`, fd));
    },
    setImageSuperseded: async (id, superseded) =>
      withAbsoluteImageUrl(baseUrl, await req<RenderImage>("PATCH", `/images/${enc(id)}`, { superseded })),
    setPinStatus: (id, status) => req("PATCH", `/pins/${enc(id)}`, { status }),
    addStudioComment: (pinId, text) => req("POST", `/pins/${enc(pinId)}/comments`, { text }),
    async getImageObjectUrl(url) {
      // Reuses the same Authorization header req() attaches elsewhere when
      // a token is present. The studio endpoint (getRoomImageFile) requires
      // it; the guest endpoint (getGuestImageFile, security: []) ignores it
      // — harmless either way, per openapi.yaml's getImageObjectUrl note.
      const headers: Record<string, string> = {};
      const t = token();
      if (t) headers["Authorization"] = `Bearer ${t}`;
      const res = await fetch(url, { headers });
      if (!res.ok) {
        let msg = res.statusText;
        try {
          msg = (await res.json()).detail ?? msg;
        } catch {
          /* ignore */
        }
        throw new ApiError(res.status, String(msg));
      }
      return URL.createObjectURL(await res.blob());
    },
    getGuestRoom: async (t) => withAbsoluteImageUrls(baseUrl, await req<RoomDetail>("GET", `/guest/${enc(t)}`)),
    createGuestPin: (t, input) => req("POST", `/guest/${enc(t)}/pins`, input),
    addGuestComment: (t, pinId, text, authorName) =>
      req("POST", `/guest/${enc(t)}/pins/${enc(pinId)}/comments`, { text, authorName }),
    approveRound: (t, authorName) => req("POST", `/guest/${enc(t)}/approve`, { authorName }),
  };
}
