import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// `useImageSrc` imports `api` from `@/lib/api`; mock just the one method it
// calls (`getImageObjectUrl`) so each test controls exactly when it
// resolves, the way `http.test.ts` controls `fetch`. `vi.hoisted` lets the
// mock factory below reference the same `vi.fn()` the tests configure.
const { getImageObjectUrl } = vi.hoisted(() => ({ getImageObjectUrl: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { getImageObjectUrl } }));

import { useImageSrc } from "./useImageSrc";

/** A promise this test resolves on demand, mirroring getImageObjectUrl's real shape. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

afterEach(() => {
  vi.unstubAllGlobals();
  getImageObjectUrl.mockReset();
});

describe("useImageSrc", () => {
  it("revokes a resolution that lands after the effect already cancelled, and never exposes it as src", async () => {
    const createObjectURL = vi.fn();
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const pending = deferred<string>();
    getImageObjectUrl.mockReturnValueOnce(pending.promise);

    const { result, unmount } = renderHook(() => useImageSrc({ url: "/images/a" }));
    expect(result.current).toBeNull();

    // Cancel (unmount) before the in-flight getImageObjectUrl promise settles.
    unmount();

    await act(async () => {
      pending.resolve("blob:stale");
      await pending.promise;
    });

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:stale");
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(result.current).toBeNull();
  });

  it("resolves normally and revokes exactly once on unmount when nothing raced it", async () => {
    const createObjectURL = vi.fn();
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const pending = deferred<string>();
    getImageObjectUrl.mockReturnValueOnce(pending.promise);

    const { result, unmount } = renderHook(() => useImageSrc({ url: "/images/a" }));

    await act(async () => {
      pending.resolve("blob:current");
      await pending.promise;
    });

    expect(result.current).toBe("blob:current");
    expect(revokeObjectURL).not.toHaveBeenCalled();

    unmount();

    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:current");
  });

  it("keeps createObjectURL/revokeObjectURL balanced across rapid image.url changes", async () => {
    let counter = 0;
    const createObjectURL = vi.fn(() => `blob:${++counter}`);
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const pendings: Array<ReturnType<typeof deferred<string>>> = [];
    getImageObjectUrl.mockImplementation(() => {
      const d = deferred<string>();
      pendings.push(d);
      return d.promise;
    });

    const { rerender, unmount } = renderHook(({ url }) => useImageSrc({ url }), {
      initialProps: { url: "/images/a" },
    });
    rerender({ url: "/images/b" });
    rerender({ url: "/images/c" });
    rerender({ url: "/images/d" });

    expect(getImageObjectUrl).toHaveBeenCalledTimes(4);

    // Settle every in-flight fetch out of request order, the way a real
    // network might. Each resolution's object URL is created (via
    // createObjectURL, as the real getImageObjectUrl does before resolving)
    // right here — the hook, or one of its cleanups, must revoke every one
    // exactly once, whether it was still current or already superseded.
    await act(async () => {
      for (const index of [2, 0, 3, 1]) {
        pendings[index]!.resolve(createObjectURL());
      }
      await Promise.all(pendings.map((p) => p.promise));
    });

    unmount();

    expect(createObjectURL).toHaveBeenCalledTimes(4);
    expect(revokeObjectURL).toHaveBeenCalledTimes(createObjectURL.mock.calls.length);
  });
});
