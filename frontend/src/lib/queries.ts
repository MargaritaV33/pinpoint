import { queryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const POLL_MS = 3000;

export const roomsQuery = () => queryOptions({ queryKey: ["rooms"], queryFn: () => api.listRooms() });
export const roomQuery = (roomId: string) =>
  queryOptions({ queryKey: ["room", roomId], queryFn: () => api.getRoom(roomId), refetchInterval: POLL_MS });
export const guestRoomQuery = (token: string) =>
  queryOptions({ queryKey: ["guest", token], queryFn: () => api.getGuestRoom(token), refetchInterval: POLL_MS, retry: false });
