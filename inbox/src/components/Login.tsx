import { type FormEvent, useState } from "react";
import { ApiError, login } from "../lib/api";
import type { Admin } from "../lib/types";
import { BrandMark } from "./BrandMark";

export function Login({ onLoggedIn }: { onLoggedIn: (admin: Admin) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLoggedIn(await login(email, password));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Connexion impossible.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <BrandMark />
          Leeral Messages
        </div>
        <h1>Connexion</h1>
        <p>Les conversations WhatsApp de Leeral, réservées à l'équipe.</p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <label className="field">
          E-mail
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="field">
          Mot de passe
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </main>
  );
}
