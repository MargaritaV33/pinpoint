import { Check } from "lucide-react";
import type { PinStatus, PinType } from "@/lib/api";
import { cn } from "@/lib/utils";

export const pinBg: Record<PinType, string> = {
  fix: "bg-pin-fix",
  question: "bg-pin-question",
  like: "bg-pin-like",
};
export const pinLabel: Record<PinType, string> = { fix: "Fix", question: "Question", like: "Like" };

interface Props {
  number?: number;
  type: PinType;
  status?: PinStatus;
  selected?: boolean;
  draft?: boolean;
  size?: "sm" | "md";
  className?: string;
}

export function PinBadge({ number, type, status, selected, draft, size = "md", className }: Props) {
  const resolved = status === "resolved";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold tabular-nums text-pin-foreground",
        size === "md" ? "h-7 w-7 text-xs" : "h-6 w-6 text-[11px]",
        pinBg[type],
        resolved && "opacity-60",
        draft && "animate-pulse",
        selected && "ring-2 ring-offset-2 ring-offset-stage ring-pin-foreground",
        className,
      )}
    >
      {draft ? "+" : resolved ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : number}
    </span>
  );
}
