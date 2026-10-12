export const MAX_RENDER_BYTES = 15 * 1024 * 1024;
export const ALLOWED_RENDER_TYPES = ["image/jpeg", "image/png"] as const;

/** Returns an error message, or null when the file is acceptable. */
export function validateRenderFile(file: { type: string; size: number; name?: string }): string | null {
  if (!(ALLOWED_RENDER_TYPES as readonly string[]).includes(file.type)) {
    return `${file.name ?? "File"} must be a JPG or PNG.`;
  }
  if (file.size > MAX_RENDER_BYTES) {
    return `${file.name ?? "File"} is larger than 15 MB.`;
  }
  return null;
}
