import type { ApiClient } from "./client";
import { formatOpenPinsExport } from "./export";
import { createSeed } from "./mock-seed";
import { ApiError } from "./types";
import type { Comment, Pin, RenderImage, Room, RoomDetail, StudioUser } from "./types";
import { validateRenderFile } from "./validation";

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export type DbRoom = Room & { ownerId: string };
export type DbPin = Omit<Pin, "comments">;
export interface MockDb {
  users: (StudioUser & { password: string })[];
  sessions: Record<string, string>;
  rooms: DbRoom[];
  images: RenderImage[];
  pins: DbPin[];
  comments: Comment[];
}

export const DB_KEY = "pinpoint.mock.db.v1";
export const SESSION_KEY = "pinpoint.mock.session";

export function createMemoryStorage(): KeyValueStorage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
  };
}

export interface MockOptions {
  /** Lazily resolved so the module is safe to import where window is absent. */
  storage?: () => KeyValueStorage | null;
  latencyMs?: number;
  now?: () => Date;
  seed?: () => MockDb;
}

function uid(prefix: string) {
  const r = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36);
  return `${prefix}_${r.replace(/-/g, "").slice(0, 12)}`;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new ApiError(400, "Could not read file"));
    reader.readAsDataURL(file);
  });
}

/**
 * Mock backend persisted to (local)Storage so a studio tab and a guest tab
 * in the same browser see each other's changes through polling.
 */
export function createMockApi(opts: MockOptions = {}): ApiClient {
  const fallback = createMemoryStorage();
  const storage = () => opts.storage?.() ?? fallback;
  const latency = opts.latencyMs ?? 0;
  const now = () => (opts.now ?? (() => new Date()))().toISOString();
  const seed = opts.seed ?? createSeed;
  // If the storage quota is exceeded (large uploads), keep the db in memory.
  let memDb: MockDb | null = null;

  const wait = () => (latency > 0 ? new Promise((r) => setTimeout(r, latency)) : Promise.resolve());

  function load(): MockDb {
    if (memDb) return memDb;
    const raw = storage().getItem(DB_KEY);
    if (raw) return JSON.parse(raw) as MockDb;
    const db = seed();
    save(db);
    return db;
  }
  function save(db: MockDb) {
    if (memDb) {
      memDb = db;
      return;
    }
    try {
      storage().setItem(DB_KEY, JSON.stringify(db));
    } catch {
      console.warn("[pinpoint mock] storage full; continuing in memory for this tab");
      memDb = db;
    }
  }
  const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));

  function requireUser(db: MockDb): StudioUser {
    const token = storage().getItem(SESSION_KEY);
    const userId = token ? db.sessions[token] : undefined;
    const user = db.users.find((u) => u.id === userId);
    if (!user) throw new ApiError(401, "Not signed in");
    return { id: user.id, email: user.email, name: user.name };
  }
  function ownedRoom(db: MockDb, user: StudioUser, roomId: string): DbRoom {
    const room = db.rooms.find((r) => r.id === roomId && r.ownerId === user.id);
    if (!room) throw new ApiError(404, "Room not found");
    return room;
  }
  function guestRoom(db: MockDb, token: string): DbRoom {
    const room = db.rooms.find((r) => r.guestToken === token);
    if (!room) throw new ApiError(404, "This review link is not valid");
    return room;
  }
  function assertOpen(room: DbRoom) {
    if (room.status === "closed") throw new ApiError(403, "This room is closed");
  }
  function toRoom({ ownerId: _o, ...r }: DbRoom): Room {
    return clone(r);
  }
  function pinWithComments(db: MockDb, p: DbPin): Pin {
    return clone({
      ...p,
      comments: db.comments.filter((c) => c.pinId === p.id).sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
    });
  }
  function detail(db: MockDb, room: DbRoom): RoomDetail {
    const images = db.images.filter((i) => i.roomId === room.id).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    const ids = new Set(images.map((i) => i.id));
    const pins = db.pins.filter((p) => ids.has(p.imageId)).map((p) => pinWithComments(db, p));
    return { room: toRoom(room), images: clone(images), pins };
  }
  function pinContext(db: MockDb, pinId: string) {
    const pin = db.pins.find((p) => p.id === pinId);
    if (!pin) throw new ApiError(404, "Pin not found");
    const image = db.images.find((i) => i.id === pin.imageId)!;
    const room = db.rooms.find((r) => r.id === image.roomId)!;
    return { pin, image, room };
  }
  function addComment(db: MockDb, pinId: string, text: string, authorName: string, authorRole: Comment["authorRole"]) {
    const t = text.trim();
    if (!t) throw new ApiError(400, "Comment cannot be empty");
    const comment: Comment = { id: uid("c"), pinId, text: t, authorName, authorRole, createdAt: now() };
    db.comments.push(comment);
    return comment;
  }

  return {
    async signup(email, password) {
      await wait();
      const db = load();
      const trimmedEmail = email.trim();
      if (!/^\S+@\S+\.\S+$/.test(trimmedEmail)) throw new ApiError(400, "A valid email is required");
      if (!password) throw new ApiError(400, "Password is required");
      if (db.users.some((u) => u.email.toLowerCase() === trimmedEmail.toLowerCase()))
        throw new ApiError(409, "An account with this email already exists");
      const user: StudioUser & { password: string } = {
        id: uid("u"),
        email: trimmedEmail,
        name: trimmedEmail.split("@")[0] ?? trimmedEmail,
        password,
      };
      db.users.push(user);
      const token = uid("t");
      db.sessions[token] = user.id;
      save(db);
      storage().setItem(SESSION_KEY, token);
      return { token, user: { id: user.id, email: user.email, name: user.name } };
    },
    async login(email, password) {
      await wait();
      const db = load();
      const user = db.users.find((u) => u.email.toLowerCase() === email.trim().toLowerCase() && u.password === password);
      if (!user) throw new ApiError(401, "Email or password is incorrect");
      const token = uid("t");
      db.sessions[token] = user.id;
      save(db);
      storage().setItem(SESSION_KEY, token);
      return { token, user: { id: user.id, email: user.email, name: user.name } };
    },
    async logout() {
      await wait();
      const db = load();
      const token = storage().getItem(SESSION_KEY);
      if (token) {
        delete db.sessions[token];
        save(db);
      }
      storage().removeItem(SESSION_KEY);
    },
    async getCurrentUser() {
      try {
        return requireUser(load());
      } catch {
        return null;
      }
    },

    async listRooms() {
      await wait();
      const db = load();
      const user = requireUser(db);
      return db.rooms
        .filter((r) => r.ownerId === user.id)
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .map((r) => {
          const ids = new Set(db.images.filter((i) => i.roomId === r.id).map((i) => i.id));
          const openPinCount = db.pins.filter((p) => ids.has(p.imageId) && p.status === "open").length;
          return { ...toRoom(r), openPinCount };
        });
    },
    async createRoom({ title, clientName }) {
      await wait();
      const db = load();
      const user = requireUser(db);
      if (!title.trim() || !clientName.trim()) throw new ApiError(400, "Title and client name are required");
      const room: DbRoom = {
        id: uid("r"),
        ownerId: user.id,
        title: title.trim(),
        clientName: clientName.trim(),
        createdAt: now(),
        status: "open",
        guestToken: uid("g"),
        approvedAt: null,
        approvedBy: null,
      };
      db.rooms.push(room);
      save(db);
      return toRoom(room);
    },
    async getRoom(roomId) {
      await wait();
      const db = load();
      return detail(db, ownedRoom(db, requireUser(db), roomId));
    },
    async closeRoom(roomId) {
      await wait();
      const db = load();
      const room = ownedRoom(db, requireUser(db), roomId);
      room.status = "closed";
      save(db);
      return toRoom(room);
    },
    async exportOpenPins(roomId) {
      await wait();
      const db = load();
      return formatOpenPinsExport(detail(db, ownedRoom(db, requireUser(db), roomId)), new Date(now()));
    },

    async uploadImage(roomId, { title, file }) {
      await wait();
      const err = validateRenderFile(file);
      if (err) throw new ApiError(400, err);
      if (!title.trim()) throw new ApiError(400, "Title is required");
      let db = load();
      const room = ownedRoom(db, requireUser(db), roomId);
      assertOpen(room);
      const url = await readFileAsDataUrl(file);
      db = load();
      const image: RenderImage = { id: uid("i"), roomId, title: title.trim(), url, superseded: false, createdAt: now() };
      db.images.push(image);
      save(db);
      return clone(image);
    },
    async setImageSuperseded(imageId, superseded) {
      await wait();
      const db = load();
      const user = requireUser(db);
      const image = db.images.find((i) => i.id === imageId);
      if (!image) throw new ApiError(404, "Image not found");
      assertOpen(ownedRoom(db, user, image.roomId));
      image.superseded = superseded;
      save(db);
      return clone(image);
    },
    async setPinStatus(pinId, status) {
      await wait();
      const db = load();
      const user = requireUser(db);
      const { pin, room } = pinContext(db, pinId);
      ownedRoom(db, user, room.id);
      assertOpen(room);
      if (pin.type === "like") throw new ApiError(400, "Like pins have no status");
      pin.status = status;
      save(db);
      return pinWithComments(db, pin);
    },
    async addStudioComment(pinId, text) {
      await wait();
      const db = load();
      const user = requireUser(db);
      const { room } = pinContext(db, pinId);
      ownedRoom(db, user, room.id);
      assertOpen(room);
      const c = addComment(db, pinId, text, user.name, "studio");
      save(db);
      return clone(c);
    },

    async getImageObjectUrl(url) {
      // Mock RenderImage.url values are already data: URIs produced by
      // uploadImage's readFileAsDataUrl — there is no network fetch to
      // perform and no Authorization header to attach, so this just hands
      // the url back unchanged. (Not a stub: this is the complete,
      // correct mock behavior, matching how an <img src="data:..."> would
      // already render it without this method existing at all.)
      await wait();
      return url;
    },
    async getGuestRoom(token) {
      await wait();
      const db = load();
      return detail(db, guestRoom(db, token));
    },
    async createGuestPin(token, input) {
      await wait();
      const db = load();
      const room = guestRoom(db, token);
      assertOpen(room);
      const image = db.images.find((i) => i.id === input.imageId && i.roomId === room.id);
      if (!image) throw new ApiError(404, "Image not found");
      if (image.superseded) throw new ApiError(409, "This render has been replaced");
      if (!input.authorName.trim()) throw new ApiError(400, "Name is required");
      if (!input.text.trim()) throw new ApiError(400, "Comment cannot be empty");
      if (![input.x, input.y].every((v) => Number.isFinite(v) && v >= 0 && v <= 100))
        throw new ApiError(400, "Pin position out of range");
      const number = db.pins.filter((p) => p.imageId === image.id).reduce((m, p) => Math.max(m, p.number), 0) + 1;
      const pin: DbPin = {
        id: uid("p"),
        imageId: image.id,
        number,
        x: input.x,
        y: input.y,
        type: input.type,
        status: input.type === "like" ? null : "open",
        createdAt: now(),
      };
      db.pins.push(pin);
      addComment(db, pin.id, input.text, input.authorName.trim(), "client");
      // New feedback after approval re-opens the round.
      if (room.status === "approved" && pin.type !== "like") room.status = "open";
      save(db);
      return pinWithComments(db, pin);
    },
    async addGuestComment(token, pinId, text, authorName) {
      await wait();
      const db = load();
      const room = guestRoom(db, token);
      assertOpen(room);
      const ctx = pinContext(db, pinId);
      if (ctx.room.id !== room.id) throw new ApiError(404, "Pin not found");
      if (!authorName.trim()) throw new ApiError(400, "Name is required");
      const c = addComment(db, pinId, text, authorName.trim(), "client");
      // A guest reply reopens a pin the studio resolved (fix/question only —
      // like pins have no status and never reach this branch).
      if (ctx.pin.status === "resolved") ctx.pin.status = "open";
      save(db);
      return clone(c);
    },
    async approveRound(token, authorName) {
      await wait();
      const db = load();
      const room = guestRoom(db, token);
      assertOpen(room);
      room.status = "approved";
      room.approvedAt = now();
      room.approvedBy = authorName.trim() || null;
      save(db);
      return toRoom(room);
    },
  };
}
