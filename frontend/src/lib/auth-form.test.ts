import { describe, expect, it, vi } from "vitest";
import { AUTH_FALLBACK_ERROR, submitAuthForm } from "./auth-form";
import { ApiError, type Session } from "./api/types";

// Satisfies submitAuthForm's Pick<ApiClient, "signup" | "login"> parameter
// type; its fields are never inspected by these tests, only that signup/
// login was called (and with what args) or that the call rejected.
const fakeSession: Session = { token: "t", user: { id: "u1", email: "a@b.com", name: "Test" } };

function fakeApi(overrides: { signup?: () => Promise<Session>; login?: () => Promise<Session> } = {}) {
  return {
    signup: vi.fn(overrides.signup ?? (() => Promise.resolve(fakeSession))),
    login: vi.fn(overrides.login ?? (() => Promise.resolve(fakeSession))),
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
