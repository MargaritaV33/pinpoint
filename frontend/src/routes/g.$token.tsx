import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { guestRoomQuery } from "@/lib/queries";
import { AppHeader, Logo, StatusBadge } from "@/components/pinpoint/AppHeader";
import { Workspace } from "@/components/pinpoint/Workspace";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const NAME_KEY = "pinpoint.guestName";

export const Route = createFileRoute("/g/$token")({
  head: () => ({
    meta: [
      { title: "Review renders — Pinpoint" },
      { name: "description", content: "Pin your feedback directly on the renders." },
      { property: "og:title", content: "You're invited to review renders — Pinpoint" },
      { property: "og:description", content: "Pin your feedback directly on the renders." },
    ],
  }),
  loader: ({ context, params }) => context.queryClient.ensureQueryData(guestRoomQuery(params.token)),
  errorComponent: ({ error }: ErrorComponentProps) => (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6">
      <Logo />
      <p className="text-muted-foreground">{error instanceof Error ? error.message : "Something went wrong"}</p>
    </div>
  ),
  component: GuestRoom,
});

function GuestRoom() {
  const { token } = Route.useParams();
  const { data } = useSuspenseQuery(guestRoomQuery(token));
  const qc = useQueryClient();
  const [name, setName] = useState<string | null>(null);
  const [askName, setAskName] = useState(false);

  useEffect(() => {
    const n = localStorage.getItem(NAME_KEY);
    if (n) setName(n);
    else setAskName(true);
  }, []);

  const refresh = () => qc.invalidateQueries({ queryKey: ["guest", token] });
  const fail = (e: Error) => {
    toast.error(e.message);
    throw e;
  };
  const closed = data.room.status === "closed";
  const author = name ?? "Guest";

  return (
    <div className="flex h-screen flex-col">
      <AppHeader linkHome={false}>
        <div className="mx-2 h-5 w-px bg-border" />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-sm font-semibold">{data.room.title}</h1>
            <StatusBadge status={data.room.status} />
          </div>
          <p className="truncate text-xs text-muted-foreground">
            Reviewing as {author} ·{" "}
            <button className="underline underline-offset-2 hover:text-foreground" onClick={() => setAskName(true)}>
              change
            </button>
          </p>
        </div>
        <div className="flex-1" />
        {!closed && (
          <Button
            variant="approve"
            size="sm"
            disabled={data.room.status === "approved"}
            onClick={() =>
              api.approveRound(token, author).then(() => {
                toast.success("Round approved — thank you!");
                refresh();
              }, fail)
            }
          >
            <CheckCircle2 className="h-4 w-4" />
            {data.room.status === "approved" ? "Round approved" : "Approve round"}
          </Button>
        )}
      </AppHeader>
      {closed && (
        <div className="flex items-center justify-center gap-2 border-b border-border bg-muted px-5 py-2.5 text-sm text-muted-foreground">
          <Lock className="h-4 w-4" /> This review room has been closed by the studio. You can still look, but no new feedback can be added.
        </div>
      )}
      <Workspace
        role="client"
        detail={data}
        readOnly={closed}
        emptyState={<p className="font-display text-3xl">The studio hasn't uploaded renders yet.</p>}
        onCreatePin={(input) =>
          api.createGuestPin(token, { ...input, authorName: author }).then((p) => {
            refresh();
            return p;
          }, fail)
        }
        onReply={(pinId, text) => api.addGuestComment(token, pinId, text, author).then(refresh, fail)}
      />
      <NameDialog
        open={askName}
        initial={name ?? ""}
        onSave={(n) => {
          localStorage.setItem(NAME_KEY, n);
          setName(n);
          setAskName(false);
        }}
        onClose={name ? () => setAskName(false) : undefined}
      />
    </div>
  );
}

function NameDialog({ open, initial, onSave, onClose }: { open: boolean; initial: string; onSave: (n: string) => void; onClose?: (() => void) | undefined }) {
  const [value, setValue] = useState(initial);
  useEffect(() => setValue(initial), [initial, open]);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent onInteractOutside={(e) => !onClose && e.preventDefault()} onEscapeKeyDown={(e) => !onClose && e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Welcome to the review</DialogTitle>
          <DialogDescription>Your name is shown next to your comments.</DialogDescription>
        </DialogHeader>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) onSave(value.trim());
          }}
        >
          <Input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder="Your name" aria-label="Your name" />
          <Button type="submit" disabled={!value.trim()}>
            Continue
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
