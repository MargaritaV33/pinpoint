import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { format } from "date-fns";
import { LogOut, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { requireStudio } from "@/lib/auth";
import { roomsQuery } from "@/lib/queries";
import { AppHeader, StatusBadge } from "@/components/pinpoint/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Review rooms — Pinpoint" },
      { name: "description", content: "Collect pinned client feedback on architectural visualization renders." },
      { property: "og:title", content: "Pinpoint — render feedback for architecture studios" },
      { property: "og:description", content: "Collect pinned client feedback on architectural visualization renders." },
    ],
  }),
  beforeLoad: requireStudio,
  loader: ({ context }) => context.queryClient.ensureQueryData(roomsQuery()),
  component: Rooms,
});

function Rooms() {
  const { user } = Route.useRouteContext();
  const { data: rooms } = useSuspenseQuery(roomsQuery());
  const navigate = useNavigate();
  const qc = useQueryClient();

  return (
    <div className="min-h-screen">
      <AppHeader>
        <div className="flex-1" />
        <span className="text-sm text-muted-foreground">{user.name}</span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          onClick={async () => {
            await api.logout();
            qc.clear();
            navigate({ to: "/login" });
          }}
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </AppHeader>
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="font-display text-5xl">Review rooms</h1>
            <p className="mt-2 text-sm text-muted-foreground">One room per review round. Share the guest link with your client.</p>
          </div>
          <CreateRoomDialog />
        </div>
        <div className="mt-10 overflow-hidden rounded-lg border border-border bg-card">
          <div className="grid grid-cols-[1fr_180px_120px_100px_90px] gap-4 border-b border-border px-5 py-2.5 text-xs uppercase tracking-wider text-muted-foreground">
            <span>Room</span>
            <span>Client</span>
            <span>Created</span>
            <span>Status</span>
            <span className="text-right">Open pins</span>
          </div>
          {rooms.length === 0 && <p className="px-5 py-10 text-center text-sm text-muted-foreground">No rooms yet.</p>}
          {rooms.map((r) => (
            <Link
              key={r.id}
              to="/rooms/$roomId"
              params={{ roomId: r.id }}
              className="grid grid-cols-[1fr_180px_120px_100px_90px] items-center gap-4 border-b border-border px-5 py-4 text-sm transition-colors last:border-0 hover:bg-muted"
            >
              <span className="truncate font-medium">{r.title}</span>
              <span className="truncate text-muted-foreground">{r.clientName}</span>
              <span className="text-muted-foreground">{format(new Date(r.createdAt), "d MMM yyyy")}</span>
              <span>
                <StatusBadge status={r.status} />
              </span>
              <span className="text-right tabular-nums">{r.openPinCount}</span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}

function CreateRoomDialog() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: () => api.createRoom({ title, clientName }),
    onSuccess: (room) => {
      qc.invalidateQueries({ queryKey: ["rooms"] });
      setOpen(false);
      navigate({ to: "/rooms/$roomId", params: { roomId: room.id } });
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" /> New room
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">New review room</DialogTitle>
        </DialogHeader>
        <form
          id="create-room"
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Lakeside Villa — Round 3" required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="client">Client name</Label>
            <Input id="client" value={clientName} onChange={(e) => setClientName(e.target.value)} required />
          </div>
        </form>
        <DialogFooter>
          <Button type="submit" form="create-room" disabled={create.isPending}>
            Create room
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
