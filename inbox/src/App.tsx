import { useEffect, useState } from "react";
import { apiConfigured, onSessionChange, refreshSession, storedAdmin } from "./lib/api";
import type { Admin } from "./lib/types";
import { Inbox } from "./components/Inbox";
import { Login } from "./components/Login";

export function App() {
  const [admin, setAdmin] = useState<Admin | null>(() => storedAdmin());
  const [checking, setChecking] = useState(() => storedAdmin() !== null);

  useEffect(() => onSessionChange(setAdmin), []);

  useEffect(() => {
    if (!checking) return;
    refreshSession()
      .then((valid) => {
        if (!valid) setAdmin(null);
      })
      .catch(() => undefined)
      .finally(() => setChecking(false));
  }, [checking]);

  if (!apiConfigured) {
    return (
      <div className="empty-pane">
        <div>
          <h2>Adresse de l'API manquante</h2>
          <p>Ajoute la variable VITE_API_URL dans les réglages du projet Vercel, puis redéploie.</p>
        </div>
      </div>
    );
  }
  if (checking) {
    return (
      <div className="empty-pane">
        <div className="spinner" role="status" aria-label="Connexion en cours" />
      </div>
    );
  }
  return admin ? <Inbox admin={admin} /> : <Login onLoggedIn={setAdmin} />;
}
