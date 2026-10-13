import { useEffect, useState } from "react";
import { api, type RenderImage } from "@/lib/api";

/**
 * Resolves `image.url` to a URL an `<img src>` can actually load, via
 * `ApiClient.getImageObjectUrl` — fetch + `Authorization` header + object
 * URL for the studio side, the url unchanged for the mock. Revokes the
 * previous object URL on cleanup and whenever `image.url` changes, so
 * switching between renders doesn't leak object URLs.
 *
 * Returns `null` while resolving (and for an empty/missing image), so
 * callers render nothing rather than a broken `<img>` icon.
 */
export function useImageSrc(image: Pick<RenderImage, "url"> | null | undefined): string | null {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!image?.url) {
      setSrc(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    api
      .getImageObjectUrl(image.url)
      .then((resolved) => {
        if (cancelled) {
          URL.revokeObjectURL(resolved);
          return;
        }
        objectUrl = resolved;
        setSrc(resolved);
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [image?.url]);

  return src;
}
