import Constants from 'expo-constants';

type Extra = { apiUrl?: string; supportWhatsApp?: string };

const extra = (Constants.expoConfig?.extra ?? {}) as Extra;

export const API_URL = (extra.apiUrl ?? '').replace(/\/+$/, '');
export const SUPPORT_WHATSAPP = (extra.supportWhatsApp ?? '').replace(/\D/g, '');
export const POLL_INTERVAL_MS = 2000;
export const MAX_PAGES = 10;
