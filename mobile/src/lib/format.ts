import type { DocumentSummary, Language } from './types';
import { colors } from './theme';

const MONTHS = [
  'janv.',
  'févr.',
  'mars',
  'avr.',
  'mai',
  'juin',
  'juil.',
  'août',
  'sept.',
  'oct.',
  'nov.',
  'déc.',
];
const MONTHS_LONG = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

export const LANGUAGE_NAMES: Record<Language, string> = {
  wo: 'Wolof',
  ff: 'Pulaar',
  sr: 'Seereer',
};

function parseDate(value: string): Date {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
}

export function shortDate(value: string): string {
  const date = parseDate(value);
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

export function longDate(value: string): string {
  const date = parseDate(value);
  return `${date.getDate()} ${MONTHS_LONG[date.getMonth()]}`;
}

export function money(amount: number): string {
  return `${amount.toLocaleString('fr-FR').replace(/[  ,]/g, ' ')} F`;
}

export function documentMeta(doc: DocumentSummary): { text: string; color: string } {
  if (doc.status === 'pending' || doc.status === 'processing') {
    return { text: 'Lecture en cours…', color: colors.muted };
  }
  if (doc.status === 'unreadable' || doc.status === 'failed') {
    return { text: 'Illisible · touche pour reprendre', color: colors.clay };
  }
  if (doc.urgency === 'urgent' && doc.urgency_label) {
    return { text: doc.urgency_label, color: colors.clay };
  }
  const parts: string[] = [];
  if (doc.main_amount_xof) parts.push(money(doc.main_amount_xof));
  if (doc.main_due_date) parts.push(`avant le ${shortDate(doc.main_due_date)}`);
  if (parts.length) {
    return { text: parts.join(' · '), color: doc.urgency === 'soon' ? colors.lightInk : colors.muted };
  }
  if (doc.urgency_label) {
    return { text: doc.urgency_label, color: doc.urgency === 'soon' ? colors.lightInk : colors.muted };
  }
  return { text: shortDate(doc.created_at), color: colors.muted };
}

export function phoneDisplay(phone: string | null): string {
  if (!phone) return '';
  const digits = phone.replace(/\D/g, '');
  if (digits.startsWith('221') && digits.length === 12) {
    const local = digits.slice(3);
    return `+221 ${local.slice(0, 2)} ${local.slice(2, 5)} ${local.slice(5, 7)} ${local.slice(7)}`;
  }
  return phone;
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count > 1 ? 's' : ''}`;
}

export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase();
}
