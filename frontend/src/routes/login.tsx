import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/pinpoint/AppHeader";
import facade from "@/assets/render-facade.jpg";

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
  const [email, setEmail] = useState("demo@pinpoint.studio");
  const [password, setPassword] = useState("pinpoint");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <h1 className="mt-10 font-display text-4xl">Studio sign in</h1>
        <p className="mt-2 text-sm text-muted-foreground">Demo account is prefilled.</p>
        <form
          className="mt-8 flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            try {
              await api.login(email, password);
              navigate({ to: "/" });
            } catch (err) {
              setError(err instanceof Error ? err.message : "Sign in failed");
            } finally {
              setBusy(false);
            }
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
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
