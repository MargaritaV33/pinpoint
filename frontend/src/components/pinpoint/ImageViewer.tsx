import { useRef } from "react";
import type { Pin, RenderImage } from "@/lib/api";
import { clientToPercent, percentToStyle, type PercentPoint } from "@/lib/pins/coords";
import { cn } from "@/lib/utils";
import { PinBadge, pinLabel } from "./PinMarker";
import type { PinType } from "@/lib/api";

interface Props {
  image: RenderImage;
  pins: Pin[];
  selectedPinId: string | null;
  draft: (PercentPoint & { type: PinType }) | null;
  onSelectPin: (id: string) => void;
  /** When undefined, clicking the image does not create pins. */
  onPlace?: ((p: PercentPoint) => void) | undefined;
}

export function ImageViewer({ image, pins, selectedPinId, draft, onSelectPin, onPlace }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);

  function handleClick(e: React.MouseEvent) {
    if (!onPlace || !imgRef.current) return;
    const p = clientToPercent(e.clientX, e.clientY, imgRef.current.getBoundingClientRect());
    if (p) onPlace(p);
  }

  return (
    <div className="flex h-full w-full items-center justify-center overflow-auto bg-stage p-6">
      <div className={cn("relative", onPlace && "cursor-crosshair")} onClick={handleClick}>
        <img
          ref={imgRef}
          src={image.url}
          alt={image.title}
          draggable={false}
          className={cn(
            "block max-h-[calc(100vh-10rem)] max-w-full select-none rounded-sm shadow-2xl",
            image.superseded && "opacity-60 grayscale-[40%]",
          )}
        />
        {pins.map((pin) => (
          <button
            key={pin.id}
            type="button"
            aria-label={`Pin ${pin.number}: ${pinLabel[pin.type]}`}
            onClick={(e) => {
              e.stopPropagation();
              onSelectPin(pin.id);
            }}
            style={percentToStyle(pin)}
            className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full shadow-pin transition-transform hover:scale-110 focus-visible:outline-none"
          >
            <PinBadge number={pin.number} type={pin.type} status={pin.status} selected={pin.id === selectedPinId} />
          </button>
        ))}
        {draft && (
          <span style={percentToStyle(draft)} className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full shadow-pin">
            <PinBadge type={draft.type} draft />
          </span>
        )}
      </div>
    </div>
  );
}
