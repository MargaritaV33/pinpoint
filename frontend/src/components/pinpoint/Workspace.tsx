import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ImageIcon, Layers } from "lucide-react";
import type { PinType, Role, RenderImage, RoomDetail } from "@/lib/api";
import type { PercentPoint } from "@/lib/pins/coords";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ImageViewer } from "./ImageViewer";
import { PIN_FILTERS, filterPins, getSessionFilter, openPinCountsByImage, setSessionFilter, type PinFilter } from "@/lib/pins/filter";
import { NewPinForm, PinList, PinThread } from "./ThreadPanel";
import { useImageSrc } from "./useImageSrc";

/** One thumbnail-rail entry. A separate component so each image gets its
 * own `useImageSrc` hook call (hooks can't be called inside `.map`). */
function ThumbnailButton({
  img,
  idx,
  active,
  openCount,
  onSelect,
}: {
  img: RenderImage;
  idx: number;
  active: boolean;
  openCount: number;
  onSelect: () => void;
}) {
  const src = useImageSrc(img);
  return (
    <button
      onClick={onSelect}
      title={img.title}
      className={cn(
        "group relative overflow-hidden rounded-md ring-2 transition",
        active ? "ring-stage-foreground" : "ring-transparent opacity-70 hover:opacity-100",
      )}
    >
      {src && <img src={src} alt="" className={cn("aspect-[4/3] w-full object-cover", img.superseded && "grayscale")} />}
      <span className="absolute left-1 top-1 rounded bg-stage/80 px-1.5 text-[10px] text-stage-foreground">{idx + 1}</span>
      {openCount > 0 && (
        <span className="absolute right-1 top-1 rounded-full bg-pin-fix px-1.5 text-[10px] font-semibold text-pin-foreground">{openCount}</span>
      )}
      {img.superseded && (
        <span className="absolute inset-x-0 bottom-0 bg-stage/85 py-0.5 text-center text-[9px] uppercase tracking-wider text-stage-foreground">
          Superseded
        </span>
      )}
    </button>
  );
}

interface Props {
  role: Role;
  detail: RoomDetail;
  readOnly: boolean;
  emptyState?: ReactNode;
  onCreatePin?: (input: { imageId: string; x: number; y: number; type: PinType; text: string }) => Promise<{ id: string }>;
  onReply: (pinId: string, text: string) => Promise<unknown>;
  onSetStatus?: (pinId: string, status: "open" | "resolved") => Promise<unknown>;
  onToggleSuperseded?: (imageId: string, superseded: boolean) => Promise<unknown>;
}

export function Workspace({ role, detail, readOnly, emptyState, onCreatePin, onReply, onSetStatus, onToggleSuperseded }: Props) {
  const { images, pins } = detail;
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PercentPoint | null>(null);
  const [draftType, setDraftType] = useState<PinType>("fix");

  useEffect(() => {
    if (activeId && images.some((i) => i.id === activeId)) return;
    setActiveId((images.find((i) => !i.superseded) ?? images[0])?.id ?? null);
  }, [images, activeId]);

  const image = images.find((i) => i.id === activeId) ?? null;
  const allImagePins = useMemo(() => pins.filter((p) => p.imageId === activeId), [pins, activeId]);
  const showFilter = role === "studio";
  const [filter, setFilterState] = useState<PinFilter>(() => (showFilter ? getSessionFilter(detail.room.id) : "all"));
  const setFilter = (f: PinFilter) => {
    setFilterState(f);
    setSessionFilter(detail.room.id, f);
  };
  const imagePins = useMemo(() => filterPins(allImagePins, filter), [allImagePins, filter]);
  const openCounts = useMemo(() => openPinCountsByImage(pins), [pins]);
  const selected = allImagePins.find((p) => p.id === selectedPinId) ?? null;
  const canPin = !!onCreatePin && !readOnly && !!image && !image.superseded;

  function switchImage(id: string) {
    setActiveId(id);
    setSelectedPinId(null);
    setDraft(null);
  }

  if (!image) {
    return <div className="flex flex-1 items-center justify-center bg-stage text-stage-foreground">{emptyState}</div>;
  }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[84px_1fr_320px] lg:grid-cols-[104px_1fr_380px]">
      {/* Image rail */}
      <nav aria-label="Renders" className="flex flex-col gap-3 overflow-y-auto border-r border-stage-muted bg-stage p-3">
        {images.map((img, idx) => (
          <ThumbnailButton
            key={img.id}
            img={img}
            idx={idx}
            active={img.id === activeId}
            openCount={img.superseded ? 0 : openCounts[img.id] ?? 0}
            onSelect={() => switchImage(img.id)}
          />
        ))}
      </nav>

      {/* Stage */}
      <section className="flex min-w-0 flex-col bg-stage">
        <div className="flex items-center gap-3 px-6 pt-4 text-stage-foreground">
          <ImageIcon className="h-4 w-4 opacity-60" />
          <h2 className="truncate text-sm font-medium">{image.title}</h2>
          {image.superseded && (
            <span className="flex items-center gap-1 rounded-full bg-stage-muted px-2 py-0.5 text-xs">
              <Layers className="h-3 w-3" /> Superseded — pins kept for reference
            </span>
          )}
          <div className="flex-1" />
          {role === "studio" && onToggleSuperseded && !readOnly && (
            <Button variant="stage" size="sm" onClick={() => onToggleSuperseded(image.id, !image.superseded)}>
              {image.superseded ? "Restore as current" : "Mark superseded"}
            </Button>
          )}
        </div>
        <div className="min-h-0 flex-1">
          <ImageViewer
            image={image}
            pins={imagePins}
            selectedPinId={selectedPinId}
            draft={draft ? { ...draft, type: draftType } : null}
            onSelectPin={(id) => {
              setDraft(null);
              setSelectedPinId(id);
            }}
            onPlace={
              canPin
                ? (p) => {
                    setSelectedPinId(null);
                    setDraft(p);
                  }
                : undefined
            }
          />
        </div>
      </section>

      {/* Side panel */}
      <aside className="min-h-0 overflow-y-auto border-l border-border bg-card">
        {draft && onCreatePin ? (
          <NewPinForm
            type={draftType}
            onTypeChange={setDraftType}
            onCancel={() => setDraft(null)}
            onSubmit={async (text) => {
              const pin = await onCreatePin({ imageId: image.id, x: draft.x, y: draft.y, type: draftType, text });
              setDraft(null);
              setSelectedPinId(pin.id);
            }}
          />
        ) : selected ? (
          <PinThread
            key={selected.id}
            pin={selected}
            role={role}
            readOnly={readOnly}
            onBack={() => setSelectedPinId(null)}
            onReply={(t) => onReply(selected.id, t)}
            onSetStatus={onSetStatus ? (s) => onSetStatus(selected.id, s) : undefined}
          />
        ) : (
          <>
          {showFilter && (
            <div role="radiogroup" aria-label="Filter pins" className="mx-4 mt-4 flex rounded-md bg-muted p-0.5 text-xs">
              {PIN_FILTERS.map((f) => (
                <button
                  key={f.value}
                  role="radio"
                  aria-checked={filter === f.value}
                  onClick={() => setFilter(f.value)}
                  className={cn(
                    "flex-1 rounded px-2 py-1 font-medium transition",
                    filter === f.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
          <PinList
            pins={imagePins}
            onSelect={setSelectedPinId}
            hint={canPin ? "Click anywhere on the render to drop a pin." : undefined}
          />
          </>
        )}
      </aside>
    </div>
  );
}
