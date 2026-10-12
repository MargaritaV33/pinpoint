import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, CheckCircle2, RotateCcw, MousePointerClick } from "lucide-react";
import type { Pin, PinType, Role } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { PinBadge, pinLabel } from "./PinMarker";

const TYPES: PinType[] = ["fix", "question", "like"];

export function NewPinForm({
  type,
  onTypeChange,
  onSubmit,
  onCancel,
}: {
  type: PinType;
  onTypeChange: (t: PinType) => void;
  onSubmit: (text: string) => Promise<unknown>;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="flex flex-col gap-4 p-5"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!text.trim()) return;
        setBusy(true);
        try {
          await onSubmit(text);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3 className="font-display text-2xl">New pin</h3>
      <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Pin type">
        {TYPES.map((t) => (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={type === t}
            onClick={() => onTypeChange(t)}
            className={cn(
              "flex items-center justify-center gap-2 rounded-md border px-2 py-2 text-sm transition-colors",
              type === t ? "border-foreground bg-secondary" : "border-border hover:bg-muted",
            )}
          >
            <PinBadge type={t} size="sm" className="h-3 w-3" />
            {pinLabel[t]}
          </button>
        ))}
      </div>
      <Textarea
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={type === "like" ? "What works well here?" : type === "question" ? "What would you like to know?" : "What should change?"}
        rows={4}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy || !text.trim()}>
          Add pin
        </Button>
      </div>
    </form>
  );
}

export function PinList({
  pins,
  onSelect,
  hint,
}: {
  pins: Pin[];
  onSelect: (id: string) => void;
  hint?: string | undefined;
}) {
  const sorted = [...pins].sort((a, b) => a.number - b.number);
  return (
    <div className="flex flex-col">
      <div className="flex items-baseline justify-between px-5 pb-3 pt-5">
        <h3 className="font-display text-2xl">Pins</h3>
        <span className="text-xs text-muted-foreground">
          {pins.filter((p) => p.status === "open").length} open
        </span>
      </div>
      {hint && (
        <p className="mx-5 mb-3 flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          <MousePointerClick className="h-3.5 w-3.5" /> {hint}
        </p>
      )}
      {sorted.length === 0 && <p className="px-5 py-6 text-sm text-muted-foreground">No pins on this render yet.</p>}
      <ul>
        {sorted.map((p) => (
          <li key={p.id}>
            <button
              onClick={() => onSelect(p.id)}
              className="flex w-full items-start gap-3 border-t border-border px-5 py-3 text-left transition-colors hover:bg-muted"
            >
              <PinBadge number={p.number} type={p.type} status={p.status} size="sm" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-sm">{p.comments[0]?.text}</span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {pinLabel[p.type]}
                  {p.status && ` · ${p.status}`} · {p.comments.length} {p.comments.length === 1 ? "comment" : "comments"}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PinThread({
  pin,
  role,
  readOnly,
  onBack,
  onReply,
  onSetStatus,
}: {
  pin: Pin;
  role: Role;
  readOnly: boolean;
  onBack: () => void;
  onReply: (text: string) => Promise<unknown>;
  onSetStatus?: ((status: "open" | "resolved") => Promise<unknown>) | undefined;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label="Back to pins">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <PinBadge number={pin.number} type={pin.type} status={pin.status} size="sm" />
        <div className="flex-1 text-sm">
          <div className="font-medium">
            Pin {pin.number} · {pinLabel[pin.type]}
          </div>
          {pin.status && <div className="text-xs capitalize text-muted-foreground">{pin.status}</div>}
        </div>
        {role === "studio" && pin.type !== "like" && onSetStatus && !readOnly && (
          <Button
            size="sm"
            variant={pin.status === "open" ? "default" : "outline"}
            onClick={() => onSetStatus(pin.status === "open" ? "resolved" : "open")}
          >
            {pin.status === "open" ? (
              <>
                <CheckCircle2 className="h-4 w-4" /> Resolve
              </>
            ) : (
              <>
                <RotateCcw className="h-4 w-4" /> Reopen
              </>
            )}
          </Button>
        )}
      </div>
      <ol className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {pin.comments.map((c) => (
          <li key={c.id} className={cn("rounded-lg px-3 py-2.5", c.authorRole === "studio" ? "bg-secondary" : "bg-card border border-border")}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
              <span className="font-medium">
                {c.authorName}
                <span className="ml-1.5 font-normal text-muted-foreground">{c.authorRole === "studio" ? "Studio" : "Client"}</span>
              </span>
              <time className="text-muted-foreground" dateTime={c.createdAt} title={new Date(c.createdAt).toLocaleString()}>
                {formatDistanceToNow(new Date(c.createdAt), { addSuffix: true })}
              </time>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{c.text}</p>
          </li>
        ))}
      </ol>
      {!readOnly && (
        <form
          className="flex flex-col gap-2 border-t border-border p-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!text.trim()) return;
            setBusy(true);
            try {
              await onReply(text);
              setText("");
            } finally {
              setBusy(false);
            }
          }}
        >
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Reply…" rows={2} />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={busy || !text.trim()}>
              Reply
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
