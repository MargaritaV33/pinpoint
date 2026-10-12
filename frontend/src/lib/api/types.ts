// Domain types shared by every ApiClient implementation. These mirror the
// future FastAPI OpenAPI contract (camelCase JSON).

export type RoomStatus = "open" | "approved" | "closed";
export type PinType = "fix" | "question" | "like";
/** like-pins carry no status (null). */
export type PinStatus = "open" | "resolved" | null;
export type AuthorRole = "studio" | "client";
export type Role = AuthorRole;

export interface StudioUser {
  id: string;
  email: string;
  name: string;
}

export interface Session {
  token: string;
  user: StudioUser;
}

export interface Room {
  id: string;
  title: string;
  clientName: string;
  createdAt: string;
  status: RoomStatus;
  guestToken: string;
  approvedAt: string | null;
  approvedBy: string | null;
}

export interface RoomSummary extends Room {
  openPinCount: number;
}

export interface RenderImage {
  id: string;
  roomId: string;
  title: string;
  url: string;
  superseded: boolean;
  createdAt: string;
}

export interface Comment {
  id: string;
  pinId: string;
  text: string;
  authorName: string;
  authorRole: AuthorRole;
  createdAt: string;
}

export interface Pin {
  id: string;
  imageId: string;
  /** Sequential per image, starting at 1. */
  number: number;
  /** Percent of image width, 0–100. */
  x: number;
  /** Percent of image height, 0–100. */
  y: number;
  type: PinType;
  status: PinStatus;
  createdAt: string;
  comments: Comment[];
}

export interface RoomDetail {
  room: Room;
  images: RenderImage[];
  pins: Pin[];
}

export interface CreateRoomInput {
  title: string;
  clientName: string;
}

export interface UploadImageInput {
  title: string;
  file: File;
}

export interface CreatePinInput {
  imageId: string;
  x: number;
  y: number;
  type: PinType;
  text: string;
  authorName: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
