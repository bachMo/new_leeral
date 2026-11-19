import type { LastMessage, Message } from "./types";

const timeFormat = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const weekdayFormat = new Intl.DateTimeFormat("fr-FR", { weekday: "long" });
const shortDateFormat = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const longDateFormat = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const DAY = 24 * 60 * 60 * 1000;

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso));
}

export function formatListDate(iso: string, now = new Date()): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY);
  if (days <= 0) return timeFormat.format(date);
  if (days === 1) return "Hier";
  if (days < 7) return capitalize(weekdayFormat.format(date));
  return shortDateFormat.format(date);
}

export function formatDayLabel(iso: string, now = new Date()): string {
  const date = new Date(iso);
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY);
  if (days <= 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return capitalize(weekdayFormat.format(date));
  return longDateFormat.format(date);
}

export function formatLongDate(iso: string | null): string {
  return iso ? longDateFormat.format(new Date(iso)) : "—";
}

export function sameDay(a: string, b: string): boolean {
  return startOfDay(new Date(a)) === startOfDay(new Date(b));
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.startsWith("221") && digits.length === 12) {
    const local = digits.slice(3);
    return `+221 ${local.slice(0, 2)} ${local.slice(2, 5)} ${local.slice(5, 7)} ${local.slice(7)}`;
  }
  return `+${digits}`;
}

export function initials(name: string | null, phone: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    const letters = parts.slice(0, 2).map((part) => part.charAt(0).toUpperCase());
    if (letters.length) return letters.join("");
  }
  return phone.replace(/\D/g, "").slice(-2);
}

export function remainingLabel(expiresAt: string | null, now = Date.now()): string {
  if (!expiresAt) return "Fenêtre fermée";
  const left = new Date(expiresAt).getTime() - now;
  if (left <= 0) return "Fenêtre fermée";
  const hours = Math.floor(left / 3_600_000);
  const minutes = Math.floor((left % 3_600_000) / 60_000);
  if (hours === 0) return `${minutes} min restantes`;
  return `${hours} h ${String(minutes).padStart(2, "0")} restantes`;
}

export function windowFraction(expiresAt: string | null, now = Date.now()): number {
  if (!expiresAt) return 0;
  const left = new Date(expiresAt).getTime() - now;
  return Math.max(0, Math.min(1, left / DAY));
}

export const LANGUAGE_NAMES: Record<string, string> = {
  wo: "Wolof",
  ff: "Pulaar",
  sr: "Seereer",
};

const TYPE_PREVIEWS: Record<string, string> = {
  image: "Photo",
  video: "Vidéo",
  audio: "Message vocal",
  document: "Document",
  sticker: "Sticker",
  location: "Position",
  contacts: "Contact",
  template: "Modèle de relance",
  unsupported: "Message non pris en charge",
};

export function previewText(message: Pick<LastMessage, "type" | "body">): string {
  if (message.type === "reaction")
    return message.body ? `A réagi ${message.body}` : "Réaction retirée";
  const label = TYPE_PREVIEWS[message.type];
  if (label && message.body) return `${label} : ${message.body}`;
  return message.body || label || "Message";
}

export function senderLabel(message: Pick<Message, "sender" | "admin_name">): string {
  if (message.sender === "contact") return "Contact";
  if (message.sender === "bot") return "Leeral";
  return message.admin_name ?? "Équipe";
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} o`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} Ko`;
  return `${(size / (1024 * 1024)).toFixed(1).replace(".", ",")} Mo`;
}

export function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
