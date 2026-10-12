import type {
  CreatePinInput,
  CreateRoomInput,
  Comment,
  Pin,
  PinStatus,
  RenderImage,
  Room,
  RoomDetail,
  RoomSummary,
  Session,
  StudioUser,
  UploadImageInput,
} from "./types";

/**
 * The single typed contract for every backend call. UI code depends only on
 * this interface; implementations: mock (default) and http (FastAPI).
 */
export interface ApiClient {
  // ---- Studio auth ----
  signup(email: string, password: string): Promise<Session>;
  login(email: string, password: string): Promise<Session>;
  logout(): Promise<void>;
  getCurrentUser(): Promise<StudioUser | null>;

  // ---- Studio rooms ----
  listRooms(): Promise<RoomSummary[]>;
  createRoom(input: CreateRoomInput): Promise<Room>;
  getRoom(roomId: string): Promise<RoomDetail>;
  closeRoom(roomId: string): Promise<Room>;
  exportOpenPins(roomId: string): Promise<string>;

  // ---- Studio images & pins ----
  uploadImage(roomId: string, input: UploadImageInput): Promise<RenderImage>;
  setImageSuperseded(imageId: string, superseded: boolean): Promise<RenderImage>;
  setPinStatus(pinId: string, status: Exclude<PinStatus, null>): Promise<Pin>;
  addStudioComment(pinId: string, text: string): Promise<Comment>;

  // ---- Guest (client) via guest token ----
  getGuestRoom(guestToken: string): Promise<RoomDetail>;
  createGuestPin(guestToken: string, input: CreatePinInput): Promise<Pin>;
  addGuestComment(guestToken: string, pinId: string, text: string, authorName: string): Promise<Comment>;
  approveRound(guestToken: string, authorName: string): Promise<Room>;
}
