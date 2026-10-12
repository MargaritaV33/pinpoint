import { redirect } from "@tanstack/react-router";
import { api } from "@/lib/api";

/** Route guard for studio pages. */
export async function requireStudio() {
  const user = await api.getCurrentUser();
  if (!user) throw redirect({ to: "/login" });
  return { user };
}
