import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "@/lib/api";
import { submitAuthForm, type AuthMode } from "@/lib/auth-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/pinpoint/AppHeader";
import facade from "@/assets/render-facade.jpg";

const DEMO_EMAIL = "demo@pinpoint.studio";
const DEMO_PASSWORD = "pinpoint";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Pinpoint" },
      { name: "description", content: "Studio sign-in for Pinpoint render reviews." },
      { property: "og:title", content: "Sign in — Pinpoint" },
      { property: "og:description", content: "Studio sign-in for Pinpoint render reviews." },
    ],
  }),
  component: Login,
});

function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggleMode() {
    setError(null);
    if (mode === "signin") {
      // Clear the demo prefill: signing up with the seeded demo account
      // would just surface a confusing 409.
      setMode("signup");
      setEmail("");
      setPassword("");
    } else {
      setMode("signin");
      setEmail(DEMO_EMAIL);
      setPassword(DEMO_PASSWORD);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_480px]">
      <div className="relative hidden bg-stage lg:block">
        <img src={facade} alt="" className="absolute inset-0 h-full w-full object-cover opacity-90" />
        <p className="absolute bottom-10 left-10 max-w-md font-display text-4xl leading-tight text-pin-foreground">
          Feedback that lands exactly where it matters.
        </p>
      </div>
      <div className="flex flex-col justify-center px-10">
        <Logo />
        <h1 className="mt-10 font-display text-4xl">{mode === "signup" ? "Create a studio account" : "Studio sign in"}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {mode === "signup" ? "Set up a new studio account." : "Demo account is prefilled."}
        </p>
        <form
          className="mt-8 flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            const result = await submitAuthForm(mode, email, password, api);
            if (result.ok) {
              navigate({ to: "/" });
            } else {
              setError(result.message);
            }
            setBusy(false);
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={busy} className="mt-2">
            {mode === "signup" ? "Create account" : "Sign in"}
          </Button>
        </form>
        <button
          type="button"
          onClick={toggleMode}
          className="mt-4 text-left text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          {mode === "signup" ? "Already have an account? Sign in" : "New studio? Create an account"}
        </button>
      </div>
    </div>
  );
}
