import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowLeft, Download, Link2, Lock, Upload } from "lucide-react";
import { toast } from "sonner";
import { api, validateRenderFile } from "@/lib/api";
import { requireStudio } from "@/lib/auth";
import { roomQuery } from "@/lib/queries";
import { AppHeader, StatusBadge } from "@/components/pinpoint/AppHeader";
import { Workspace } from "@/components/pinpoint/Workspace";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export const Route = createFileRoute("/rooms/$roomId")({
  head: () => ({
    meta: [
      { title: "Review room — Pinpoint" },
      { name: "description", content: "Review pinned client feedback on your renders." },
      { property: "og:title", content: "Review room — Pinpoint" },
      { property: "og:description", content: "Review pinned client feedback on your renders." },
    ],
  }),
  beforeLoad: requireStudio,
  loader: ({ context, params }) => context.queryClient.ensureQueryData(roomQuery(params.roomId)),
  errorComponent: ({ error }: ErrorComponentProps) => (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <p className="text-muted-foreground">{error instanceof Error ? error.message : "Something went wrong"}</p>
      <Link to="/" className="text-sm underline">
        Back to rooms
      </Link>
    </div>
  ),
  component: StudioRoom,
});

function StudioRoom() {
  const { roomId } = Route.useParams();
  const { data } = useSuspenseQuery(roomQuery(roomId));
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["room", roomId] });
    qc.invalidateQueries({ queryKey: ["rooms"] });
  };
  const onError = (e: Error) => toast.error(e.message);
  const closed = data.room.status === "closed";

  const close = useMutation({ mutationFn: () => api.closeRoom(roomId), onSuccess: refresh, onError });

  async function copyLink() {
    const url = `${window.location.origin}/g/${data.room.guestToken}`;
    await navigator.clipboard.writeText(url).catch(() => {});
    toast.success("Guest link copied", { description: url });
  }
  async function exportPins() {
    try {
      const text = await api.exportOpenPins(roomId);
      const blob = new Blob([text], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${data.room.title.replace(/[^\w-]+/g, "-").toLowerCase()}-open-pins.txt`;
      a.click();
      URL.revokeObjectURL(a.href);
      await navigator.clipboard.writeText(text).catch(() => {});
      toast.success("Open pins exported", { description: "Downloaded and copied to clipboard." });
    } catch (e) {
      onError(e as Error);
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <AppHeader>
        <Link to="/" className="text-muted-foreground hover:text-foreground" aria-label="Back to rooms">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-sm font-semibold">{data.room.title}</h1>
            <StatusBadge status={data.room.status} />
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {data.room.clientName}
            {data.room.status === "approved" && data.room.approvedBy && ` · approved by ${data.room.approvedBy}`}
          </p>
        </div>
        <div className="flex-1" />
        {!closed && <UploadDialog roomId={roomId} onDone={refresh} />}
        <Button variant="outline" size="sm" onClick={copyLink}>
          <Link2 className="h-4 w-4" /> Guest link
        </Button>
        <Button variant="outline" size="sm" onClick={exportPins}>
          <Download className="h-4 w-4" /> Export open pins
        </Button>
        {!closed && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm">
                <Lock className="h-4 w-4" /> Close room
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Close this room?</AlertDialogTitle>
                <AlertDialogDescription>
                  The room becomes read-only. Your client can still view pins but can no longer comment.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => close.mutate()}>Close room</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </AppHeader>
      {closed && (
        <div className="border-b border-border bg-muted px-5 py-2 text-center text-xs text-muted-foreground">
          This room is closed and read-only.
        </div>
      )}
      <Workspace
        role="studio"
        detail={data}
        readOnly={closed}
        emptyState={
          <div className="text-center">
            <p className="font-display text-3xl">No renders yet</p>
            <p className="mt-2 text-sm opacity-70">Upload a JPG or PNG to start the review.</p>
          </div>
        }
        onReply={(pinId, text) => api.addStudioComment(pinId, text).then(refresh, onError)}
        onSetStatus={(pinId, s) => api.setPinStatus(pinId, s).then(refresh, onError)}
        onToggleSuperseded={(id, v) => api.setImageSuperseded(id, v).then(refresh, onError)}
      />
    </div>
  );
}

function UploadDialog({ roomId, onDone }: { roomId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<{ file: File; title: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pick(files: FileList | null) {
    if (!files) return;
    const next: { file: File; title: string }[] = [];
    for (const f of Array.from(files)) {
      const err = validateRenderFile(f);
      if (err) {
        setError(err);
        continue;
      }
      next.push({ file: f, title: f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ") });
    }
    setItems((prev) => [...prev, ...next]);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) {
          setItems([]);
          setError(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Upload className="h-4 w-4" /> Upload renders
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Upload renders</DialogTitle>
        </DialogHeader>
        <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-input bg-muted px-4 py-8 text-sm text-muted-foreground hover:bg-accent">
          <Upload className="h-5 w-5" />
          Choose JPG or PNG files (max 15 MB each)
          <input
            type="file"
            accept="image/jpeg,image/png"
            multiple
            className="sr-only"
            onChange={(e) => {
              setError(null);
              pick(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="grid max-h-64 gap-3 overflow-y-auto">
          {items.map((it, i) => (
            <div key={i} className="grid gap-1">
              <Label htmlFor={`t${i}`} className="truncate text-xs text-muted-foreground">
                {it.file.name}
              </Label>
              <Input
                id={`t${i}`}
                value={it.title}
                onChange={(e) => setItems((p) => p.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                placeholder="Title"
              />
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button
            disabled={busy || items.length === 0 || items.some((i) => !i.title.trim())}
            onClick={async () => {
              setBusy(true);
              try {
                for (const it of items) await api.uploadImage(roomId, it);
                toast.success(`${items.length} render${items.length > 1 ? "s" : ""} uploaded`);
                onDone();
                setOpen(false);
                setItems([]);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Upload {items.length > 0 && `(${items.length})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
