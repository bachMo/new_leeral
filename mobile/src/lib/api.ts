import { File } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_URL } from './config';
import { readJson, removeValue, writeJson } from './storage';
import type {
  Conversation,
  DocumentDetail,
  DocumentPage,
  Exchange,
  Language,
  LearningOverview,
  LocalFile,
  Me,
  Message,
  OtpChallenge,
  Payment,
  Plan,
  PracticeAnswer,
  PracticeRound,
  Prompt,
  TextLanguage,
  Tokens,
  Transcription,
  Word,
  Writing,
  WritingType,
} from './types';

const SESSION_KEY = 'leeral.session';
const NETWORK_ERROR = 'NETWORK_ERROR';

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly retryable: boolean = false,
    readonly fields: Record<string, unknown> = {},
  ) {
    super(message);
  }

  get promptKey(): string {
    return `error.${this.code.toLowerCase()}`;
  }
}

type Session = { access: string; refresh: string };

let session: Session | null = null;
let markLoaded: () => void = () => undefined;
const sessionLoaded = new Promise<void>((resolve) => {
  markLoaded = resolve;
});
let sessionListener: ((tokens: Tokens | null) => void) | null = null;

export async function loadSession(): Promise<Session | null> {
  try {
    session = await readJson<Session>(SESSION_KEY);
    return session;
  } finally {
    markLoaded();
  }
}

export async function saveTokens(tokens: Tokens): Promise<void> {
  session = { access: tokens.access_token, refresh: tokens.refresh_token };
  await writeJson(SESSION_KEY, session);
}

export async function clearSession(): Promise<void> {
  session = null;
  await removeValue(SESSION_KEY);
}

export function onSessionChange(listener: (tokens: Tokens | null) => void): void {
  sessionListener = listener;
}

export function platformName(): 'android' | 'ios' | 'web' {
  if (Platform.OS === 'ios') return 'ios';
  if (Platform.OS === 'android') return 'android';
  return 'web';
}

type Body = { json?: unknown; form?: FormData };

const TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 180_000;

async function send(method: string, path: string, body: Body, auth: boolean): Promise<Response> {
  if (!API_URL) {
    throw new ApiError(
      'API_URL_MISSING',
      "L'adresse de l'API manque. Ajoute LEERAL_API_URL dans le fichier .env.",
      0,
    );
  }
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'ngrok-skip-browser-warning': '1',
  };
  if (auth && session) headers.Authorization = `Bearer ${session.access}`;
  let payload: BodyInit | undefined;
  if (body.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body.json);
  } else if (body.form) {
    payload = body.form;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), body.form ? UPLOAD_TIMEOUT_MS : TIMEOUT_MS);
  try {
    return await fetch(`${API_URL}/v1${path}`, { method, headers, body: payload, signal: controller.signal });
  } catch (error) {
    const timedOut = controller.signal.aborted;
    if (__DEV__) {
      console.warn(
        `[leeral api] ${method} ${API_URL}/v1${path} ${timedOut ? 'timeout' : 'failed'}: ${String(error)}`,
      );
    }
    if (timedOut) {
      throw new ApiError('TIMEOUT', 'Leeral met trop de temps à répondre. Réessaie.', 0, true);
    }
    throw new ApiError(NETWORK_ERROR, 'Pas de connexion avec Leeral. Vérifie ton internet.', 0, true);
  } finally {
    clearTimeout(timer);
  }
}

async function toError(response: Response): Promise<ApiError> {
  try {
    const data = (await response.json()) as {
      error?: {
        code: string;
        message: string;
        retryable: boolean;
        fields?: Record<string, unknown>;
      };
    };
    if (data.error) {
      return new ApiError(
        data.error.code,
        data.error.message,
        response.status,
        data.error.retryable,
        data.error.fields ?? {},
      );
    }
  } catch {
    return new ApiError('INTERNAL_ERROR', 'Un problème est survenu. Réessaie.', response.status, true);
  }
  return new ApiError('INTERNAL_ERROR', 'Un problème est survenu. Réessaie.', response.status, true);
}

type RefreshOutcome = 'renewed' | 'rejected' | 'offline';

let refreshing: Promise<RefreshOutcome> | null = null;

async function refreshTokens(): Promise<RefreshOutcome> {
  if (!session) return 'rejected';
  refreshing ??= (async (): Promise<RefreshOutcome> => {
    try {
      const response = await send(
        'POST',
        '/auth/refresh',
        { json: { refresh_token: session?.refresh } },
        false,
      );
      if (response.status === 400 || response.status === 401 || response.status === 403) return 'rejected';
      if (!response.ok) return 'offline';
      const tokens = (await response.json()) as Tokens;
      await saveTokens(tokens);
      sessionListener?.(tokens);
      return 'renewed';
    } catch {
      return 'offline';
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function request<T>(method: string, path: string, body: Body = {}, auth = true): Promise<T> {
  if (auth) await sessionLoaded;
  const token = session?.access;
  let response = await send(method, path, body, auth);
  if (response.status === 401 && auth && token) {
    if (session && session.access !== token) {
      response = await send(method, path, body, auth);
    } else {
      const outcome = await refreshTokens();
      if (outcome === 'renewed') {
        response = await send(method, path, body, auth);
      } else if (outcome === 'offline') {
        throw new ApiError(NETWORK_ERROR, 'Pas de connexion avec Leeral. Vérifie ton internet.', 0, true);
      } else if (session?.access === token) {
        await clearSession();
        sessionListener?.(null);
      }
    }
  }
  if (!response.ok) {
    const failure = await toError(response);
    if (__DEV__) console.warn(`[leeral api] ${method} ${path} -> ${response.status} ${failure.code}`);
    throw failure;
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function appendFile(form: FormData, field: string, file: LocalFile): Promise<void> {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(file.uri)).blob();
    form.append(field, blob, file.name);
    return;
  }
  const part = { name: file.name, type: file.type, bytes: () => new File(file.uri).bytes() };
  form.append(field, part as unknown as Blob);
}

function device() {
  return { platform: platformName() };
}

export const api = {
  prompts: (language: Language) => request<Prompt[]>('GET', `/prompts?language=${language}`, {}, false),

  startGuest: (deviceId: string, language: Language) =>
    request<Tokens>('POST', '/auth/guest', { json: { device_id: deviceId, language, ...device() } }, false),
  requestOtp: (phone: string) =>
    request<OtpChallenge>('POST', '/auth/otp/request', { json: { phone_number: phone } }, false),
  verifyOtp: (phone: string, code: string, language: Language) =>
    request<Tokens>('POST', '/auth/otp/verify', {
      json: { phone_number: phone, code, language, ...device() },
    }),
  logout: () => request<void>('POST', '/auth/logout'),

  me: () => request<Me>('GET', '/me'),
  updateMe: (patch: { first_name?: string; language?: Language; accept_terms?: boolean }) =>
    request<Me>('PATCH', '/me', { json: patch }),

  uploadDocument: async (files: LocalFile[]) => {
    const form = new FormData();
    for (const file of files) await appendFile(form, 'files', file);
    return request<DocumentDetail>('POST', '/documents', { form });
  },
  documents: (limit = 20, category?: string) =>
    request<DocumentPage>('GET', `/documents?limit=${limit}${category ? `&category=${category}` : ''}`),
  document: (id: string) => request<DocumentDetail>('GET', `/documents/${id}`),
  deleteDocument: (id: string) => request<void>('DELETE', `/documents/${id}`),
  retryDocument: (id: string) => request<DocumentDetail>('POST', `/documents/${id}/retry`),
  simplify: (id: string) =>
    request<{ status: 'ready' | 'pending' }>('POST', `/documents/${id}/explanations`, {
      json: { variant: 'simple' },
    }),
  openConversation: (documentId: string) =>
    request<Conversation>('POST', `/documents/${documentId}/conversation`),

  messages: (conversationId: string) =>
    request<Message[]>('GET', `/conversations/${conversationId}/messages`),
  ask: async (
    conversationId: string,
    question: { audio?: LocalFile; text?: string; textLanguage?: TextLanguage; suggestedId?: string },
  ) => {
    const form = new FormData();
    if (question.audio) await appendFile(form, 'audio', question.audio);
    if (question.text) form.append('text', question.text);
    if (question.textLanguage) form.append('text_language', question.textLanguage);
    if (question.suggestedId) form.append('suggested_question_id', question.suggestedId);
    return request<Exchange>('POST', `/conversations/${conversationId}/messages`, { form });
  },

  transcribe: async (audio: LocalFile) => {
    const form = new FormData();
    await appendFile(form, 'audio', audio);
    return request<Transcription>('POST', '/speech/transcriptions', { form });
  },

  writings: () => request<Writing[]>('GET', '/writings?limit=50'),
  writing: (id: string) => request<Writing>('GET', `/writings/${id}`),
  startWriting: (type: WritingType) => request<Writing>('POST', '/writings', { json: { type } }),
  answerWriting: async (
    id: string,
    answer: { audio?: LocalFile; text?: string; textLanguage?: TextLanguage },
  ) => {
    const form = new FormData();
    if (answer.audio) await appendFile(form, 'audio', answer.audio);
    if (answer.text) form.append('text', answer.text);
    if (answer.textLanguage) form.append('text_language', answer.textLanguage);
    return request<Message>('POST', `/writings/${id}/answers`, { form });
  },
  confirmWriting: (id: string, accepted: boolean) =>
    request<Writing>('POST', `/writings/${id}/confirm`, { json: { accepted } }),
  skipWriting: (id: string) => request<Writing>('POST', `/writings/${id}/skip`),

  learningOverview: () => request<LearningOverview>('GET', '/learning/overview'),
  words: () => request<Word[]>('GET', '/learning/words?limit=100'),
  startPractice: () => request<PracticeRound>('POST', '/learning/sessions'),
  answerPractice: (sessionId: string, wordId: string, chosenWordId: string) =>
    request<PracticeAnswer>('POST', `/learning/sessions/${sessionId}/answers`, {
      json: { word_id: wordId, chosen_word_id: chosenWordId },
    }),
  finishPractice: (sessionId: string) => request<unknown>('POST', `/learning/sessions/${sessionId}/finish`),

  plans: () => request<Plan[]>('GET', '/billing/plans', {}, false),
  checkout: () => request<Payment>('POST', '/billing/checkout', { json: { method: 'wave' } }),
  simulatePayment: (token: string) =>
    request<Payment>('POST', `/billing/payments/${token}/simulate`, { json: { outcome: 'success' } }),
};

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError('INTERNAL_ERROR', 'Un problème est survenu. Réessaie.', 0, true);
}
