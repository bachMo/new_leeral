export type Sender = "contact" | "bot" | "admin";
export type ThreadFilter = "all" | "unread" | "open" | "paused";

export interface Admin {
  id: string;
  email: string;
  name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  admin: Admin;
}

export interface LastMessage {
  id: string;
  sender: Sender;
  type: string;
  body: string | null;
  status: string;
  created_at: string;
}

export interface Thread {
  id: string;
  wa_phone: string;
  phone: string;
  name: string | null;
  language: string | null;
  last_message: LastMessage;
  unread_count: number;
  last_inbound_at: string | null;
  window_expires_at: string | null;
  window_open: boolean;
  bot_paused: boolean;
  bot_paused_manual: boolean;
  bot_paused_until: string | null;
}

export interface ThreadPage {
  items: Thread[];
  has_more: boolean;
  unread_threads: number;
  server_time: string;
}

export interface ThreadDetail extends Thread {
  user_id: string | null;
  whatsapp_name: string | null;
  first_name: string | null;
  registered: boolean;
  plan: { code: string; expires_at: string | null } | null;
  documents_count: number;
  first_contact_at: string | null;
  last_seen_at: string | null;
  channel_number: string;
}

export interface Quoted {
  id: string;
  sender: Sender;
  type: string;
  body: string | null;
}

export interface Message {
  id: string;
  wa_message_id: string;
  direction: "inbound" | "outbound";
  sender: Sender;
  admin_name: string | null;
  type: string;
  body: string | null;
  status: string;
  error: string | null;
  has_media: boolean;
  media_mime: string | null;
  filename: string | null;
  voice: boolean;
  template_name: string | null;
  location: {
    latitude: number;
    longitude: number;
    name?: string | null;
    address?: string | null;
  } | null;
  contacts: { name: string; phones: string[] }[];
  reply_to: Quoted | null;
  reaction: { target_id: string | null; target_wa_id: string; emoji: string } | null;
  created_at: string;
  updated_at: string;
}

export interface MessagePage {
  items: Message[];
  has_more: boolean;
  server_time: string;
}

export interface MediaLink {
  url: string;
  mime_type: string | null;
  filename: string | null;
}

export type OutgoingKind =
  "text" | "image" | "video" | "audio" | "voice" | "document" | "contact" | "template";

export interface ApiErrorBody {
  code: string;
  message: string;
  fields?: Record<string, unknown>;
}
