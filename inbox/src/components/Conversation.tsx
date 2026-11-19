import { ArrowLeft, Info, Send } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  getThread,
  listMessages,
  markRead,
  type OutgoingPayload,
  sendMessage,
  setBot,
} from "../lib/api";
import {
  formatDayLabel,
  formatPhone,
  formatTime,
  LANGUAGE_NAMES,
  remainingLabel,
  sameDay,
  windowFraction,
} from "../lib/format";
import { useInterval } from "../lib/hooks";
import type { Message, OutgoingKind, Thread, ThreadDetail } from "../lib/types";
import { Avatar } from "./Avatar";
import { Composer, type ComposerHandle } from "./Composer";
import { ContactPanel } from "./ContactPanel";
import { Lightbox } from "./Lightbox";
import { MessageBubble } from "./MessageBubble";
import { useToast } from "./Toasts";

const OVERLAP_MS = 5 * 60 * 1000;
const GROUP_GAP_MS = 5 * 60 * 1000;
const NEAR_BOTTOM_PX = 140;

interface PendingSend {
  message: Message;
  payload: OutgoingPayload;
  status: "sending" | "failed";
  error: string | null;
}

interface ConversationProps {
  threadId: string;
  thread: Thread | null;
  visible: boolean;
  now: number;
  onBack: () => void;
  onThreadChange: (thread: Thread) => void;
  onActivity: () => void;
}

const KIND_TYPES: Record<OutgoingKind, string> = {
  text: "text",
  image: "image",
  video: "video",
  audio: "audio",
  voice: "audio",
  document: "document",
  contact: "contacts",
  template: "template",
};

function byTime(a: Message, b: Message): number {
  return a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id);
}

function merge(current: Message[], incoming: Message[]): Message[] {
  if (!incoming.length) return current;
  const map = new Map(current.map((message) => [message.id, message]));
  incoming.forEach((message) => map.set(message.id, message));
  return Array.from(map.values()).sort(byTime);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const reason = error.body.fields?.reason;
    return typeof reason === "string" && reason ? `${error.message} (${reason})` : error.message;
  }
  return error instanceof Error ? error.message : "Envoi impossible.";
}

export function Conversation(props: ConversationProps) {
  const { threadId, visible, now, onThreadChange, onActivity } = props;
  const toast = useToast();
  const [summary, setSummary] = useState<Thread | null>(props.thread);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasOlder, setHasOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [pending, setPending] = useState<PendingSend[]>([]);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [botBusy, setBotBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const composer = useRef<ComposerHandle>(null);
  const cursor = useRef<string | null>(null);
  const nearBottom = useRef(true);
  const lastInboundSeen = useRef<string | null>(null);

  useEffect(() => {
    if (props.thread) setSummary(props.thread);
  }, [props.thread]);

  const header = summary ?? detail;

  const scrollToBottom = useCallback((smooth = false) => {
    requestAnimationFrame(() => {
      const element = scroller.current;
      if (element)
        element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    });
  }, []);

  const applyThread = useCallback(
    (thread: Thread) => {
      setSummary(thread);
      onThreadChange(thread);
    },
    [onThreadChange],
  );

  const refreshDetail = useCallback(async () => {
    try {
      const fresh = await getThread(threadId);
      setDetail(fresh);
      setSummary((current) => current ?? fresh);
    } catch {
      return;
    }
  }, [threadId]);

  const acknowledge = useCallback(
    async (items: Message[]) => {
      const latestInbound = [...items].reverse().find((item) => item.direction === "inbound");
      if (!latestInbound || latestInbound.id === lastInboundSeen.current) return;
      lastInboundSeen.current = latestInbound.id;
      try {
        applyThread(await markRead(threadId));
      } catch {
        lastInboundSeen.current = null;
      }
    },
    [applyThread, threadId],
  );

  useEffect(() => {
    let active = true;
    setMessages(null);
    setLoadError(null);
    listMessages(threadId)
      .then((page) => {
        if (!active) return;
        setMessages(page.items);
        setHasOlder(page.has_more);
        cursor.current = page.server_time;
        scrollToBottom();
        if (document.visibilityState === "visible") void acknowledge(page.items);
      })
      .catch((error: unknown) => active && setLoadError(errorText(error)));
    void refreshDetail();
    return () => {
      active = false;
    };
  }, [threadId, scrollToBottom, refreshDetail, acknowledge]);

  const poll = useCallback(async () => {
    if (!cursor.current || messages === null) return;
    const since = new Date(new Date(cursor.current).getTime() - OVERLAP_MS).toISOString();
    try {
      const page = await listMessages(threadId, { updatedAfter: since });
      cursor.current = page.server_time;
      if (!page.items.length) return;
      const known = new Set(messages.map((message) => message.id));
      const fresh = page.items.filter((message) => !known.has(message.id));
      setMessages((current) => merge(current ?? [], page.items));
      if (fresh.length) {
        if (nearBottom.current) scrollToBottom(true);
        if (visible) void acknowledge(fresh);
      }
    } catch {
      return;
    }
  }, [threadId, messages, visible, acknowledge, scrollToBottom]);

  useEffect(() => {
    const element = scroller.current;
    const inner = element?.firstElementChild;
    if (!element || !inner || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (nearBottom.current) element.scrollTop = element.scrollHeight;
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, [messages === null]);

  useInterval(() => void poll(), visible ? 3_000 : 15_000);
  useInterval(() => void refreshDetail(), 60_000);

  useEffect(() => {
    if (visible && messages) void acknowledge(messages);
  }, [visible]);

  async function loadOlder() {
    if (!messages?.length || loadingOlder) return;
    const element = scroller.current;
    const previousHeight = element?.scrollHeight ?? 0;
    setLoadingOlder(true);
    try {
      const page = await listMessages(threadId, { before: messages[0]?.id });
      setMessages((current) => merge(current ?? [], page.items));
      setHasOlder(page.has_more);
      requestAnimationFrame(() => {
        if (element) element.scrollTop += element.scrollHeight - previousHeight;
      });
    } catch (error) {
      toast(errorText(error), { error: true });
    } finally {
      setLoadingOlder(false);
    }
  }

  function onScroll() {
    const element = scroller.current;
    if (!element) return;
    nearBottom.current =
      element.scrollHeight - element.scrollTop - element.clientHeight < NEAR_BOTTOM_PX;
    if (element.scrollTop < 60 && hasOlder && !loadingOlder) void loadOlder();
  }

  async function deliver(entry: PendingSend) {
    try {
      const sent = await sendMessage(threadId, entry.payload);
      setPending((items) => items.filter((item) => item.message.id !== entry.message.id));
      setMessages((current) => merge(current ?? [], [sent]));
      scrollToBottom(true);
      onActivity();
      void refreshDetail();
    } catch (error) {
      setPending((items) =>
        items.map((item) =>
          item.message.id === entry.message.id
            ? { ...item, status: "failed", error: errorText(error) }
            : item,
        ),
      );
      if (error instanceof ApiError && error.code === "WHATSAPP_WINDOW_CLOSED")
        void refreshDetail();
    }
  }

  function send(payload: OutgoingPayload) {
    const quoted = payload.replyTo
      ? messages?.find((message) => message.id === payload.replyTo)
      : null;
    const optimistic: Message = {
      id: `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      wa_message_id: "",
      direction: "outbound",
      sender: "admin",
      admin_name: "Vous",
      type: KIND_TYPES[payload.kind],
      body:
        payload.kind === "contact"
          ? null
          : payload.kind === "template"
            ? null
            : (payload.text ?? null),
      status: "sent",
      error: null,
      has_media: false,
      media_mime: null,
      filename: payload.kind === "voice" ? "Message vocal" : (payload.fileName ?? null),
      voice: payload.kind === "voice",
      template_name: payload.kind === "template" ? "leeral_rappel" : null,
      location: null,
      contacts:
        payload.kind === "contact"
          ? [{ name: payload.contactName ?? "", phones: [payload.contactPhone ?? ""] }]
          : [],
      reply_to: quoted
        ? { id: quoted.id, sender: quoted.sender, type: quoted.type, body: quoted.body }
        : null,
      reaction: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    const entry: PendingSend = { message: optimistic, payload, status: "sending", error: null };
    setPending((items) => [...items, entry]);
    nearBottom.current = true;
    scrollToBottom(true);
    void deliver(entry);
  }

  function retry(id: string) {
    const entry = pending.find((item) => item.message.id === id);
    if (!entry) return;
    const next: PendingSend = { ...entry, status: "sending", error: null };
    setPending((items) => items.map((item) => (item.message.id === id ? next : item)));
    void deliver(next);
  }

  async function toggleBot() {
    if (!header) return;
    setBotBusy(true);
    try {
      const updated = await setBot(threadId, !header.bot_paused);
      applyThread(updated);
      toast(
        updated.bot_paused
          ? "Leeral ne répond plus à ce contact."
          : "Leeral répond de nouveau à ce contact.",
      );
    } catch (error) {
      toast(errorText(error), { error: true });
    } finally {
      setBotBusy(false);
    }
  }

  function sendTemplate() {
    const confirmed = window.confirm(
      "Envoyer le modèle de relance « leeral_rappel » ? WhatsApp le facture comme une nouvelle conversation.",
    );
    if (confirmed) send({ kind: "template" });
  }

  function jumpTo(id: string) {
    const element = document.getElementById(`m-${id}`);
    if (!element) {
      toast("Ce message est plus ancien. Remonte la conversation pour le charger.");
      return;
    }
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlight(id);
    window.setTimeout(() => setHighlight((current) => (current === id ? null : current)), 1600);
  }

  const timeline = useMemo(() => {
    const loaded = messages ?? [];
    const ids = new Set(loaded.map((message) => message.id));
    const reactions = new Map<string, string>();
    const orphanReactions: Message[] = [];
    for (const message of loaded) {
      if (message.type !== "reaction" || !message.reaction) continue;
      const target = message.reaction.target_id;
      if (target && ids.has(target)) {
        if (message.reaction.emoji) reactions.set(target, message.reaction.emoji);
        else reactions.delete(target);
      } else if (message.reaction.emoji) {
        orphanReactions.push(message);
      }
    }
    const visibleMessages = loaded.filter(
      (message) => message.type !== "reaction" || orphanReactions.includes(message),
    );
    const all = [...visibleMessages, ...pending.map((item) => item.message)];
    return { items: all, reactions };
  }, [messages, pending]);

  const windowOpen = Boolean(
    header?.window_expires_at && new Date(header.window_expires_at).getTime() > now,
  );
  const fraction = windowFraction(header?.window_expires_at ?? null, now);
  const pendingById = new Map(pending.map((item) => [item.message.id, item]));

  const pauseNote = header?.bot_paused
    ? header.bot_paused_manual
      ? "Leeral est en pause pour ce contact"
      : header.bot_paused_until
        ? `Leeral reprend à ${formatTime(header.bot_paused_until)}`
        : null
    : null;

  return (
    <div className="conversation">
      <div className="conversation-body" style={{ gridRow: "1 / -1" }}>
        <div
          className="conversation-column"
          onDragOver={(event) => {
            if (!windowOpen || !event.dataTransfer.types.includes("Files")) return;
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(event) => {
            if (event.currentTarget === event.target) setDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files[0];
            if (file && windowOpen) composer.current?.stageFile(file);
          }}
          style={{ position: "relative", gridTemplateRows: "auto auto 1fr auto" }}
        >
          <header className="conversation-head">
            <button
              className="icon-button back-button"
              onClick={props.onBack}
              aria-label="Retour à la liste"
            >
              <ArrowLeft size={20} />
            </button>
            <button
              className="head-identity"
              onClick={() => setPanelOpen(true)}
              aria-label="Voir la fiche du contact"
            >
              {header && (
                <Avatar
                  name={header.name}
                  phone={header.phone}
                  windowExpiresAt={header.window_expires_at}
                  now={now}
                />
              )}
              <span className="head-text">
                <span className="head-name" style={{ display: "block" }}>
                  {header ? (header.name ?? formatPhone(header.phone)) : "Chargement…"}
                </span>
                {header && (
                  <span className="head-sub" style={{ display: "block" }}>
                    {[
                      header.name ? formatPhone(header.phone) : null,
                      header.language ? (LANGUAGE_NAMES[header.language] ?? header.language) : null,
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                )}
              </span>
            </button>
            {header && (
              <button
                className="bot-switch"
                role="switch"
                aria-checked={!header.bot_paused}
                disabled={botBusy}
                onClick={() => void toggleBot()}
                title={
                  header.bot_paused
                    ? "Réactiver les réponses automatiques"
                    : "Mettre Leeral en pause"
                }
              >
                <span className="track" aria-hidden="true" />
                <span className="bot-label">
                  {header.bot_paused ? "Leeral en pause" : "Leeral répond"}
                </span>
              </button>
            )}
            <button
              className="icon-button"
              onClick={() => setPanelOpen((open) => !open)}
              aria-label="Fiche du contact"
              aria-pressed={panelOpen}
            >
              <Info size={20} />
            </button>
          </header>
          <div
            className={`window-bar${windowOpen && fraction < 2 / 24 ? " is-low" : ""}`}
            role="status"
            aria-label="Fenêtre de réponse"
          >
            <span>{windowOpen ? "Fenêtre ouverte" : "Fenêtre fermée"}</span>
            <span className="window-meter" aria-hidden="true">
              <span style={{ width: `${fraction * 100}%` }} />
            </span>
            {windowOpen && (
              <strong>{remainingLabel(header?.window_expires_at ?? null, now)}</strong>
            )}
            {pauseNote && <span className="pause-note">{pauseNote}</span>}
          </div>
          <div className="messages" ref={scroller} onScroll={onScroll}>
            <div className="messages-inner">
              {loadError && (
                <div className="list-state" role="alert">
                  <strong>Conversation indisponible</strong>
                  {loadError}
                </div>
              )}
              {!messages && !loadError && (
                <div className="list-state">
                  <div
                    className="spinner"
                    style={{ margin: "0 auto" }}
                    role="status"
                    aria-label="Chargement"
                  />
                </div>
              )}
              {messages && hasOlder && (
                <button
                  className="ghost-button older"
                  onClick={() => void loadOlder()}
                  disabled={loadingOlder}
                >
                  {loadingOlder ? "Chargement…" : "Messages plus anciens"}
                </button>
              )}
              {timeline.items.map((message, index) => {
                const previous = timeline.items[index - 1];
                const newDay = !previous || !sameDay(previous.created_at, message.created_at);
                if (message.type === "reaction") {
                  return (
                    <Fragment key={message.id}>
                      {newDay && (
                        <div className="day-label">{formatDayLabel(message.created_at)}</div>
                      )}
                      <div className="system-line">
                        Le contact a réagi {message.reaction?.emoji} à un message plus ancien
                      </div>
                    </Fragment>
                  );
                }
                const startsGroup =
                  newDay ||
                  !previous ||
                  previous.sender !== message.sender ||
                  previous.admin_name !== message.admin_name ||
                  new Date(message.created_at).getTime() - new Date(previous.created_at).getTime() >
                    GROUP_GAP_MS;
                const entry = pendingById.get(message.id);
                return (
                  <Fragment key={message.id}>
                    {newDay && (
                      <div className="day-label">{formatDayLabel(message.created_at)}</div>
                    )}
                    <MessageBubble
                      message={message}
                      startsGroup={startsGroup}
                      reaction={timeline.reactions.get(message.id) ?? null}
                      highlighted={highlight === message.id}
                      pending={entry?.status}
                      pendingError={entry?.error}
                      onReply={(target) => setReplyTo(target)}
                      onJump={jumpTo}
                      onZoom={setZoom}
                      onRetry={() => retry(message.id)}
                      onDiscard={() =>
                        setPending((items) =>
                          items.filter((item) => item.message.id !== message.id),
                        )
                      }
                    />
                  </Fragment>
                );
              })}
            </div>
          </div>
          {windowOpen ? (
            <Composer
              ref={composer}
              windowOpen={windowOpen}
              replyTo={replyTo}
              onCancelReply={() => setReplyTo(null)}
              onSend={send}
              onError={(text) => toast(text, { error: true })}
            />
          ) : (
            <div className="composer">
              <div className="window-closed">
                <p>
                  {header?.last_inbound_at
                    ? "Le contact n'a pas écrit depuis plus de 24 h. WhatsApp n'autorise que le modèle de relance tant qu'il ne répond pas."
                    : "Ce contact n'a encore jamais écrit. Seul le modèle de relance peut lui être envoyé."}
                </p>
                <button className="primary-button" onClick={sendTemplate}>
                  <Send size={16} aria-hidden="true" />
                  Envoyer le modèle de relance
                </button>
              </div>
            </div>
          )}
          {dragging && <div className="drop-zone">Dépose le fichier pour l'envoyer</div>}
        </div>
        {panelOpen && (
          <ContactPanel detail={detail} now={now} onClose={() => setPanelOpen(false)} />
        )}
      </div>
      {zoom && <Lightbox url={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
