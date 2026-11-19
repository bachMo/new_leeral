import { Copy, ExternalLink, X } from "lucide-react";
import { formatLongDate, formatPhone, LANGUAGE_NAMES, remainingLabel } from "../lib/format";
import type { ThreadDetail } from "../lib/types";
import { Avatar } from "./Avatar";
import { useToast } from "./Toasts";

interface ContactPanelProps {
  detail: ThreadDetail | null;
  now: number;
  onClose: () => void;
}

export function ContactPanel({ detail, now, onClose }: ContactPanelProps) {
  const toast = useToast();

  async function copyPhone() {
    if (!detail) return;
    try {
      await navigator.clipboard.writeText(detail.phone);
      toast("Numéro copié.");
    } catch {
      toast("Copie impossible dans ce navigateur.", { error: true });
    }
  }

  return (
    <aside className="contact-panel" aria-label="Fiche du contact">
      <div className="contact-panel-head">
        <span>Fiche du contact</span>
        <button className="icon-button" onClick={onClose} aria-label="Fermer la fiche">
          <X size={20} />
        </button>
      </div>
      {!detail ? (
        <div className="list-state">
          <div
            className="spinner"
            style={{ margin: "0 auto" }}
            role="status"
            aria-label="Chargement"
          />
        </div>
      ) : (
        <>
          <div className="contact-hero">
            <Avatar
              name={detail.name}
              phone={detail.phone}
              windowExpiresAt={detail.window_expires_at}
              now={now}
              large
            />
            <h2>{detail.name ?? "Contact sans nom"}</h2>
            <div className="phone">{formatPhone(detail.phone)}</div>
            <div className="contact-actions">
              <button className="ghost-button" onClick={() => void copyPhone()}>
                <Copy size={15} /> Copier
              </button>
              <a
                className="ghost-button"
                href={`https://wa.me/${detail.wa_phone}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: "none" }}
              >
                <ExternalLink size={15} /> WhatsApp
              </a>
            </div>
          </div>
          <dl className="facts">
            <div>
              <dt>Fenêtre de 24 h</dt>
              <dd>{remainingLabel(detail.window_expires_at, now)}</dd>
            </div>
            <div>
              <dt>Nom WhatsApp</dt>
              <dd>{detail.whatsapp_name ?? "—"}</dd>
            </div>
            {detail.first_name && (
              <div>
                <dt>Prénom dans l'app</dt>
                <dd>{detail.first_name}</dd>
              </div>
            )}
            <div>
              <dt>Langue</dt>
              <dd>
                {detail.language ? (LANGUAGE_NAMES[detail.language] ?? detail.language) : "—"}
              </dd>
            </div>
            <div>
              <dt>Formule</dt>
              <dd className={detail.plan?.code === "leeral_plus" ? "plan-plus" : undefined}>
                {detail.plan?.code === "leeral_plus"
                  ? `Leeral+ jusqu'au ${formatLongDate(detail.plan.expires_at)}`
                  : detail.plan
                    ? "Gratuite"
                    : "—"}
              </dd>
            </div>
            <div>
              <dt>Documents expliqués</dt>
              <dd>{detail.documents_count}</dd>
            </div>
            <div>
              <dt>Compte dans l'app</dt>
              <dd>{detail.registered ? "Oui" : "Non, WhatsApp uniquement"}</dd>
            </div>
            <div>
              <dt>Premier message</dt>
              <dd>{formatLongDate(detail.first_contact_at)}</dd>
            </div>
            <div>
              <dt>Dernière activité</dt>
              <dd>{formatLongDate(detail.last_seen_at)}</dd>
            </div>
            <div>
              <dt>Numéro Leeral</dt>
              <dd>{detail.channel_number}</dd>
            </div>
          </dl>
        </>
      )}
    </aside>
  );
}
