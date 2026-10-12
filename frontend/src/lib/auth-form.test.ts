import { describe, expect, it, vi } from "vitest";
import { AUTH_FALLBACK_ERROR, submitAuthForm } from "./auth-form";
import { ApiError } from "./api/types";

function fakeApi(overrides: { signup?: () => Promise<unknown>; login?: () => Promise<unknown> } = {}) {
  return {
    signup: vi.fn(overrides.signup ?? (() => Promise.resolve({}))),
    login: vi.fn(overrides.login ?? (() => Promise.resolve({}))),
  };
}

describe("submitAuthForm", () => {
  it("signin mode calls login, not signup", async () => {
    const api = fakeApi();
    const result = await submitAuthForm("signin", "a@b.com", "pw", api);
    expect(result).toEqual({ ok: true });
    expect(api.login).toHaveBeenCalledWith("a@b.com", "pw");
    expect(api.signup).not.toHaveBeenCalled();
  });

  it("signup mode calls signup, not login", async () => {
    const api = fakeApi();
    const result = await submitAuthForm("signup", "a@b.com", "pw", api);
    expect(result).toEqual({ ok: true });
    expect(api.signup).toHaveBeenCalledWith("a@b.com", "pw");
    expect(api.login).not.toHaveBeenCalled();
  });

  it("surfaces an ApiError(409) message exactly", async () => {
    const api = fakeApi({ signup: () => Promise.reject(new ApiError(409, "An account with this email already exists.")) });
    const result = await submitAuthForm("signup", "a@b.com", "pw", api);
    expect(result).toEqual({ ok: false, message: "An account with this email already exists." });
  });

  it("surfaces an ApiError(400) message exactly", async () => {
    const api = fakeApi({ login: () => Promise.reject(new ApiError(400, "Password is required.")) });
    const result = await submitAuthForm("signin", "a@b.com", "", api);
    expect(result).toEqual({ ok: false, message: "Password is required." });
  });

  it("falls back to a generic message for a non-ApiError throw", async () => {
    const api = fakeApi({ login: () => Promise.reject(new Error("socket hang up")) });
    const result = await submitAuthForm("signin", "a@b.com", "pw", api);
    expect(result).toEqual({ ok: false, message: AUTH_FALLBACK_ERROR });
  });

  it("falls back to a generic message for a thrown non-Error value", async () => {
    const api = fakeApi({ signup: () => Promise.reject("nope") });
    const result = await submitAuthForm("signup", "a@b.com", "pw", api);
    expect(result).toEqual({ ok: false, message: AUTH_FALLBACK_ERROR });
  });
});
