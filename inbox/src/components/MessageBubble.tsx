import {
  AlertCircle,
  Check,
  CheckCheck,
  Clock,
  Reply,
  RotateCw,
  Send,
  Trash2,
  UserRound,
} from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { formatPhone, formatTime, senderLabel } from "../lib/format";
import type { Message, Quoted } from "../lib/types";
import { MediaContent } from "./MediaContent";

const URL_PATTERN = /(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)])/g;

function Linkified({ text }: { text: string }) {
  const parts = text.split(URL_PATTERN);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer nofollow">
            {part}
          </a>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function StatusTick({ message, pending }: { message: Message; pending?: "sending" | "failed" }) {
  if (pending === "sending") return <Clock size={13} aria-label="Envoi en cours" />;
  if (pending === "failed")
    return <AlertCircle size={14} className="tick-failed" aria-label="Échec" />;
  if (message.direction === "inbound") return null;
  switch (message.status) {
    case "read":
      return <CheckCheck size={15} className="tick-read" aria-label="Lu" />;
    case "delivered":
      return <CheckCheck size={15} aria-label="Reçu" />;
    case "failed":
      return <AlertCircle size={14} className="tick-failed" aria-label="Non distribué" />;
    default:
      return <Check size={15} aria-label="Envoyé" />;
  }
}

function quoteAuthor(quote: Quoted): string {
  if (quote.sender === "contact") return "Contact";
  return quote.sender === "bot" ? "Leeral" : "Équipe";
}

const QUOTE_TYPES: Record<string, string> = {
  image: "Photo",
  video: "Vidéo",
  audio: "Message vocal",
  document: "Document",
  sticker: "Sticker",
  location: "Position",
  contacts: "Contact",
  template: "Modèle de relance",
};

function Body({ message, onZoom }: { message: Message; onZoom: (url: string) => void }) {
  const blocks: ReactNode[] = [];
  const mediaTypes = ["image", "video", "audio", "document", "sticker"];
  if (message.has_media && mediaTypes.includes(message.type)) {
    blocks.push(<MediaContent key="media" message={message} onZoom={onZoom} />);
  } else if (mediaTypes.includes(message.type) && !message.has_media) {
    blocks.push(
      <div key="no-media" className="file-sub">
        {message.id.startsWith("pending-")
          ? `Envoi : ${message.filename ?? QUOTE_TYPES[message.type] ?? "fichier"}`
          : "Média non conservé"}
      </div>,
    );
  }
  if (message.location) {
    const { latitude, longitude, name, address } = message.location;
    blocks.push(
      <div key="place" className="place-card">
        <strong>{name ?? "Position partagée"}</strong>
        {address && <span className="file-sub">{address}</span>}
        <a
          href={`https://www.google.com/maps?q=${latitude},${longitude}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Voir sur la carte
        </a>
      </div>,
    );
  }
  message.contacts.forEach((contact, index) =>
    blocks.push(
      <div key={`contact-${index}`} className="contact-card">
        <strong style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <UserRound size={16} aria-hidden="true" />
          {contact.name || "Contact"}
        </strong>
        {contact.phones.map((phone) => (
          <a
            key={phone}
            href={`https://wa.me/${phone.replace(/\D/g, "")}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {formatPhone(phone)}
          </a>
        ))}
      </div>,
    ),
  );
  if (message.type === "template") {
    blocks.push(
      <div key="template" className="template-note">
        <Send size={15} aria-hidden="true" />
        Modèle « {message.template_name} » envoyé
      </div>,
    );
  }
  const showText =
    message.body &&
    message.type !== "contacts" &&
    message.type !== "location" &&
    !(message.type === "document" && message.body === message.filename);
  if (showText && message.body) {
    blocks.push(
      <div key="text" className="bubble-text">
        <Linkified text={message.body} />
      </div>,
    );
  }
  if (message.type === "interactive" && message.direction === "outbound") {
    blocks.push(
      <div key="buttons" className="file-sub">
        Avec boutons de réponse
      </div>,
    );
  }
  if (message.type === "unsupported") {
    blocks.push(
      <div key="unsupported" className="file-sub">
        Type de message non pris en charge par WhatsApp Cloud API
      </div>,
    );
  }
  return <>{blocks}</>;
}

interface MessageBubbleProps {
  message: Message;
  startsGroup: boolean;
  reaction: string | null;
  highlighted: boolean;
  pending?: "sending" | "failed";
  pendingError?: string | null;
  onReply: (message: Message) => void;
  onJump: (id: string) => void;
  onZoom: (url: string) => void;
  onRetry?: () => void;
  onDiscard?: () => void;
}

export function MessageBubble(props: MessageBubbleProps) {
  const { message, pending } = props;
  const out = message.direction === "outbound";
  const failed = pending === "failed" || message.status === "failed";
  const classes = [
    "row",
    out ? "is-out" : "",
    message.sender === "bot" ? "is-bot" : "",
    message.sender === "admin" ? "is-admin" : "",
    props.startsGroup ? "starts-group" : "",
    failed ? "is-failed" : "",
    props.highlighted ? "is-highlighted" : "",
    props.reaction ? "has-reaction" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} id={`m-${message.id}`}>
      {props.startsGroup && out && <div className="row-label">{senderLabel(message)}</div>}
      <div className="bubble-line">
        <div className="bubble">
          {message.reply_to && (
            <button
              className={`quote from-${message.reply_to.sender}`}
              onClick={() => message.reply_to && props.onJump(message.reply_to.id)}
            >
              <strong>{quoteAuthor(message.reply_to)}</strong>
              <span>
                {message.reply_to.body ?? QUOTE_TYPES[message.reply_to.type] ?? "Message"}
              </span>
            </button>
          )}
          <Body message={message} onZoom={props.onZoom} />
          <div className="bubble-foot">
            <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
            <StatusTick message={message} pending={pending} />
          </div>
          {props.reaction && <span className="reaction-badge">{props.reaction}</span>}
        </div>
        {!pending && (
          <button
            className="icon-button bubble-action"
            onClick={() => props.onReply(message)}
            aria-label="Répondre à ce message"
          >
            <Reply size={16} />
          </button>
        )}
      </div>
      {pending === "failed" && (
        <div className="bubble-error" role="alert">
          {props.pendingError ?? "Envoi impossible."}{" "}
          <button
            className="icon-button"
            style={{ width: 28, height: 28 }}
            onClick={props.onRetry}
            aria-label="Réessayer"
          >
            <RotateCw size={14} />
          </button>
          <button
            className="icon-button"
            style={{ width: 28, height: 28 }}
            onClick={props.onDiscard}
            aria-label="Supprimer"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
      {!pending && message.status === "failed" && (
        <div className="bubble-error">
          Non distribué{message.error ? ` : ${message.error}` : ""}
        </div>
      )}
    </div>
  );
}
