import { Bell, BellOff, Check, CheckCheck, LogOut, Menu, PauseCircle, Search } from "lucide-react";
import { useState } from "react";
import { formatListDate, formatPhone, previewText } from "../lib/format";
import type { Admin, Thread, ThreadFilter } from "../lib/types";
import { Avatar } from "./Avatar";
import { BrandMark } from "./BrandMark";

const FILTERS: { value: ThreadFilter; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "unread", label: "Non lues" },
  { value: "open", label: "Ouvertes" },
  { value: "paused", label: "En pause" },
];

interface ThreadListProps {
  admin: Admin;
  threads: Thread[] | null;
  error: string | null;
  hasMore: boolean;
  unreadThreads: number;
  filter: ThreadFilter;
  query: string;
  selectedId: string | null;
  now: number;
  notificationsOn: boolean;
  onFilter: (filter: ThreadFilter) => void;
  onQuery: (query: string) => void;
  onSelect: (id: string) => void;
  onLoadMore: () => void;
  onToggleNotifications: () => void;
  onLogout: () => void;
}

function LastStatus({ thread }: { thread: Thread }) {
  const last = thread.last_message;
  if (last.sender === "contact") return null;
  if (last.status === "read") return <CheckCheck size={15} className="tick-read" aria-label="Lu" />;
  if (last.status === "delivered") return <CheckCheck size={15} aria-label="Reçu" />;
  return <Check size={15} aria-label="Envoyé" />;
}

export function ThreadList(props: ThreadListProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { threads } = props;

  return (
    <aside className="sidebar" aria-label="Conversations">
      <div className="sidebar-head" style={{ position: "relative" }}>
        <div className="brand">
          <BrandMark />
          Messages
          {props.unreadThreads > 0 && (
            <span className="unread-total" aria-label={`${props.unreadThreads} non lues`}>
              {props.unreadThreads}
            </span>
          )}
        </div>
        <button
          className="icon-button"
          aria-label="Menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <Menu size={20} />
        </button>
        {menuOpen && (
          <div className="menu-pop" role="menu" onMouseLeave={() => setMenuOpen(false)}>
            <div className="menu-who">
              <strong>{props.admin.name}</strong>
              {props.admin.email}
            </div>
            <button
              role="menuitem"
              onClick={() => {
                props.onToggleNotifications();
                setMenuOpen(false);
              }}
            >
              {props.notificationsOn ? <BellOff size={18} /> : <Bell size={18} />}
              {props.notificationsOn ? "Couper les notifications" : "Activer les notifications"}
            </button>
            <button role="menuitem" onClick={props.onLogout}>
              <LogOut size={18} />
              Se déconnecter
            </button>
          </div>
        )}
      </div>
      <label className="search">
        <span className="sr-only">Rechercher</span>
        <Search size={17} aria-hidden="true" />
        <input
          type="search"
          placeholder="Nom ou numéro"
          value={props.query}
          onChange={(event) => props.onQuery(event.target.value)}
        />
      </label>
      <div className="filters" role="group" aria-label="Filtrer">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            aria-pressed={props.filter === item.value}
            onClick={() => props.onFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="thread-list">
        {props.error && !threads && (
          <div className="list-state" role="alert">
            <strong>Liste indisponible</strong>
            {props.error}
          </div>
        )}
        {!threads && !props.error && (
          <div className="list-state">
            <div
              className="spinner"
              style={{ margin: "0 auto" }}
              role="status"
              aria-label="Chargement"
            />
          </div>
        )}
        {threads && threads.length === 0 && (
          <div className="list-state">
            <strong>
              {props.query || props.filter !== "all" ? "Aucun résultat" : "Aucune conversation"}
            </strong>
            {props.query || props.filter !== "all"
              ? "Change la recherche ou le filtre."
              : "Les messages envoyés au numéro WhatsApp de Leeral apparaîtront ici."}
          </div>
        )}
        {threads?.map((thread) => (
          <button
            key={thread.id}
            className={`thread-item${thread.unread_count > 0 ? " has-unread" : ""}`}
            aria-current={thread.id === props.selectedId}
            onClick={() => props.onSelect(thread.id)}
          >
            <Avatar
              name={thread.name}
              phone={thread.phone}
              windowExpiresAt={thread.window_expires_at}
              now={props.now}
            />
            <div className="thread-main">
              <div className="thread-name">{thread.name ?? formatPhone(thread.phone)}</div>
              <div className="thread-preview">
                <LastStatus thread={thread} />
                <span>
                  {thread.last_message.sender === "bot" && "Leeral : "}
                  {thread.last_message.sender === "admin" && "Vous : "}
                  {previewText(thread.last_message)}
                </span>
              </div>
            </div>
            <div className="thread-meta">
              <span className="thread-time">
                {formatListDate(thread.last_message.created_at, new Date(props.now))}
              </span>
              <span className="thread-badges">
                {thread.bot_paused && (
                  <span className="paused-dot" title="Bot en pause">
                    <PauseCircle size={14} aria-label="Bot en pause" />
                  </span>
                )}
                {thread.unread_count > 0 && (
                  <span className="unread-count" aria-label={`${thread.unread_count} non lus`}>
                    {thread.unread_count}
                  </span>
                )}
              </span>
            </div>
          </button>
        ))}
        {threads && props.hasMore && (
          <button className="ghost-button load-more" onClick={props.onLoadMore}>
            Afficher plus
          </button>
        )}
      </div>
    </aside>
  );
}
