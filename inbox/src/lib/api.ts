import type {
  Admin,
  ApiErrorBody,
  MediaLink,
  Message,
  MessagePage,
  OutgoingKind,
  Thread,
  ThreadDetail,
  ThreadFilter,
  ThreadPage,
  TokenResponse,
} from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
const SESSION_KEY = "leeral-inbox-session";

interface StoredSession {
  refreshToken: string;
  admin: Admin;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ApiErrorBody,
  ) {
    super(body.message);
  }

  get code(): string {
    return this.body.code;
  }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const sessionListeners = new Set<(admin: Admin | null) => void>();

function readStored(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function writeStored(session: StoredSession | null): void {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    return;
  }
}

function applyTokens(tokens: TokenResponse): Admin {
  accessToken = tokens.access_token;
  writeStored({ refreshToken: tokens.refresh_token, admin: tokens.admin });
  return tokens.admin;
}

function endSession(): void {
  accessToken = null;
  writeStored(null);
  sessionListeners.forEach((listener) => listener(null));
}

export function onSessionChange(listener: (admin: Admin | null) => void): () => void {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

export function storedAdmin(): Admin | null {
  return readStored()?.admin ?? null;
}

export const apiConfigured = API_URL.length > 0;

async function errorBody(response: Response): Promise<ApiErrorBody | null> {
  try {
    const payload = (await response.json()) as { error?: ApiErrorBody };
    return payload.error ?? null;
  } catch {
    return null;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await errorBody(response);
  if (body) return new ApiError(response.status, body);
  return new ApiError(response.status, {
    code: response.status >= 500 ? "SERVER_ERROR" : "HTTP_ERROR",
    message:
      response.status >= 500
        ? "Le serveur ne répond pas correctement. Réessaie dans un instant."
        : `Erreur ${response.status}.`,
  });
}

async function rawFetch(path: string, init: RequestInit = {}, withAuth = true): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("ngrok-skip-browser-warning", "1");
  if (withAuth && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  try {
    return await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, {
      code: "NETWORK",
      message: "Impossible de joindre le serveur Leeral. Vérifie ta connexion.",
    });
  }
}

export async function refreshSession(): Promise<boolean> {
  if (refreshing) return refreshing;
  const stored = readStored();
  if (!stored) return false;
  refreshing = (async () => {
    try {
      const response = await rawFetch(
        "/v1/admin/auth/refresh",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: stored.refreshToken }),
        },
        false,
      );
      if (response.status === 401) {
        endSession();
        return false;
      }
      if (!response.ok) throw await parseError(response);
      applyTokens((await response.json()) as TokenResponse);
      return true;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!accessToken && !(await refreshSession())) {
    throw new ApiError(401, { code: "UNAUTHENTICATED", message: "Connecte-toi pour continuer." });
  }
  let response = await rawFetch(path, init);
  if (response.status === 401) {
    if (await refreshSession()) response = await rawFetch(path, init);
    else throw new ApiError(401, { code: "UNAUTHENTICATED", message: "Ta session a expiré." });
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export async function login(email: string, password: string): Promise<Admin> {
  const response = await rawFetch("/v1/admin/auth/login", json("POST", { email, password }), false);
  if (!response.ok) throw await parseError(response);
  const admin = applyTokens((await response.json()) as TokenResponse);
  sessionListeners.forEach((listener) => listener(admin));
  return admin;
}

export async function logout(): Promise<void> {
  try {
    if (accessToken) await rawFetch("/v1/admin/auth/logout", { method: "POST" });
  } finally {
    endSession();
  }
}

export function listThreads(params: {
  q?: string;
  filter: ThreadFilter;
  offset?: number;
}): Promise<ThreadPage> {
  const search = new URLSearchParams({ filter: params.filter, offset: String(params.offset ?? 0) });
  if (params.q) search.set("q", params.q);
  return request(`/v1/admin/inbox/threads?${search}`);
}

export function getThread(id: string): Promise<ThreadDetail> {
  return request(`/v1/admin/inbox/threads/${id}`);
}

export function listMessages(
  threadId: string,
  params: { before?: string; updatedAfter?: string } = {},
): Promise<MessagePage> {
  const search = new URLSearchParams();
  if (params.before) search.set("before", params.before);
  if (params.updatedAfter) search.set("updated_after", params.updatedAfter);
  const query = search.toString();
  return request(`/v1/admin/inbox/threads/${threadId}/messages${query ? `?${query}` : ""}`);
}

export function markRead(threadId: string): Promise<Thread> {
  return request(`/v1/admin/inbox/threads/${threadId}/read`, { method: "POST" });
}

export function setBot(threadId: string, paused: boolean): Promise<Thread> {
  return request(`/v1/admin/inbox/threads/${threadId}/bot`, json("PUT", { paused }));
}

export function mediaLink(messageId: string): Promise<MediaLink> {
  return request(`/v1/admin/inbox/messages/${messageId}/media`);
}

export interface OutgoingPayload {
  kind: OutgoingKind;
  text?: string;
  file?: File | Blob;
  fileName?: string;
  replyTo?: string;
  contactName?: string;
  contactPhone?: string;
}

export function sendMessage(threadId: string, payload: OutgoingPayload): Promise<Message> {
  const form = new FormData();
  form.set("type", payload.kind);
  if (payload.text) form.set("text", payload.text);
  if (payload.replyTo) form.set("reply_to", payload.replyTo);
  if (payload.contactName) form.set("contact_name", payload.contactName);
  if (payload.contactPhone) form.set("contact_phone", payload.contactPhone);
  if (payload.file) form.set("file", payload.file, payload.fileName ?? "fichier");
  return request(`/v1/admin/inbox/threads/${threadId}/messages`, { method: "POST", body: form });
}
