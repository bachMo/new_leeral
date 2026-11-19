import { MessagesSquare } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, listThreads, logout } from "../lib/api";
import { formatPhone, previewText } from "../lib/format";
import { useInterval, useNow, usePageVisible } from "../lib/hooks";
import type { Admin, Thread, ThreadFilter } from "../lib/types";
import { Conversation } from "./Conversation";
import { ThreadList } from "./ThreadList";
import { ToastProvider } from "./Toasts";

const NOTIFY_KEY = "leeral-inbox-notifications";
const TITLE = "Leeral Messages";

function threadFromHash(): string | null {
  const match = window.location.hash.match(/^#\/c\/([0-9a-f-]{36})$/);
  return match?.[1] ?? null;
}

function writeNotifyPreference(on: boolean): void {
  try {
    localStorage.setItem(NOTIFY_KEY, on ? "on" : "off");
  } catch {
    return;
  }
}

function readNotifyPreference(): boolean {
  try {
    return localStorage.getItem(NOTIFY_KEY) === "on";
  } catch {
    return false;
  }
}

export function Inbox({ admin }: { admin: Admin }) {
  const [threads, setThreads] = useState<Thread[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [pages, setPages] = useState(1);
  const [unreadThreads, setUnreadThreads] = useState(0);
  const [filter, setFilter] = useState<ThreadFilter>("all");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(() => threadFromHash());
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [notificationsOn, setNotificationsOn] = useState(
    () =>
      readNotifyPreference() && "Notification" in window && Notification.permission === "granted",
  );
  const visible = usePageVisible();
  const now = useNow(30_000);
  const lastSeen = useRef<Map<string, string> | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(id);
  }, [query]);

  useEffect(() => {
    const onHash = () => setSelectedId(threadFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const notify = useCallback(
    (fresh: Thread[]) => {
      const previous = lastSeen.current;
      const next = new Map(fresh.map((thread) => [thread.id, thread.last_message.id]));
      lastSeen.current = next;
      if (!previous || !notificationsOn || !("Notification" in window)) return;
      for (const thread of fresh) {
        const last = thread.last_message;
        if (last.sender !== "contact" || previous.get(thread.id) === last.id) continue;
        if (visible && thread.id === selectedId) continue;
        const notification = new Notification(thread.name ?? formatPhone(thread.phone), {
          body: previewText(last),
          tag: thread.id,
          icon: "/icon.svg",
        });
        notification.onclick = () => {
          window.focus();
          window.location.hash = `#/c/${thread.id}`;
          notification.close();
        };
      }
    },
    [notificationsOn, selectedId, visible],
  );

  const refresh = useCallback(async () => {
    const current = ++requestId.current;
    try {
      const collected: Thread[] = [];
      let more = false;
      let unread = 0;
      for (let page = 0; page < pages; page += 1) {
        const result = await listThreads({ q: debouncedQuery, filter, offset: collected.length });
        collected.push(...result.items);
        more = result.has_more;
        unread = result.unread_threads;
        if (!result.has_more) break;
      }
      if (current !== requestId.current) return;
      setThreads(collected);
      setHasMore(more);
      setUnreadThreads(unread);
      setError(null);
      if (filter === "all" && !debouncedQuery) notify(collected);
    } catch (caught) {
      if (current !== requestId.current) return;
      if (caught instanceof ApiError && caught.status === 401) return;
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    }
  }, [debouncedQuery, filter, pages, notify]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useInterval(() => void refresh(), visible ? 5_000 : 30_000);

  useEffect(() => {
    document.title = unreadThreads > 0 ? `(${unreadThreads}) ${TITLE}` : TITLE;
  }, [unreadThreads]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedThread(null);
      return;
    }
    const fromList = threads?.find((thread) => thread.id === selectedId);
    if (fromList) setSelectedThread(fromList);
  }, [selectedId, threads]);

  const select = (id: string) => {
    window.location.hash = `#/c/${id}`;
  };

  const updateThread = useCallback((thread: Thread) => {
    setThreads((items) => {
      if (!items) return items;
      const exists = items.some((item) => item.id === thread.id);
      const updated = exists
        ? items.map((item) => (item.id === thread.id ? thread : item))
        : [thread, ...items];
      return updated.sort((a, b) =>
        b.last_message.created_at.localeCompare(a.last_message.created_at),
      );
    });
    setSelectedThread((current) => (current?.id === thread.id ? thread : current));
  }, []);

  async function toggleNotifications() {
    if (notificationsOn) {
      setNotificationsOn(false);
      writeNotifyPreference(false);
      return;
    }
    if (!("Notification" in window)) return;
    const permission = await Notification.requestPermission();
    const granted = permission === "granted";
    setNotificationsOn(granted);
    writeNotifyPreference(granted);
  }

  return (
    <ToastProvider>
      <div className={`inbox${selectedId ? " has-selection" : ""}`}>
        <ThreadList
          admin={admin}
          threads={threads}
          error={error}
          hasMore={hasMore}
          unreadThreads={unreadThreads}
          filter={filter}
          query={query}
          selectedId={selectedId}
          now={now}
          notificationsOn={notificationsOn}
          onFilter={(value) => {
            setFilter(value);
            setPages(1);
          }}
          onQuery={(value) => {
            setQuery(value);
            setPages(1);
          }}
          onSelect={select}
          onLoadMore={() => setPages((count) => count + 1)}
          onToggleNotifications={() => void toggleNotifications()}
          onLogout={() => void logout()}
        />
        <section className="conversation-pane" style={{ minWidth: 0, minHeight: 0 }}>
          {selectedId ? (
            <Conversation
              key={selectedId}
              threadId={selectedId}
              thread={selectedThread}
              visible={visible}
              now={now}
              onBack={() => {
                window.location.hash = "";
              }}
              onThreadChange={updateThread}
              onActivity={() => void refresh()}
            />
          ) : (
            <div className="empty-pane">
              <div>
                <MessagesSquare size={44} strokeWidth={1.5} aria-hidden="true" />
                <h2>Choisis une conversation</h2>
                <p>
                  Tu peux répondre tant que la fenêtre de 24 h est ouverte. L'anneau autour de
                  chaque contact montre le temps qu'il reste.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </ToastProvider>
  );
}
