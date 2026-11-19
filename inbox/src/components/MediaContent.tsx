import { FileText, ImageOff, Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useMedia } from "../lib/hooks";
import type { Message } from "../lib/types";

function useOnScreen<T extends Element>(): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || seen) return;
    if (!("IntersectionObserver" in window)) {
      setSeen(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [seen]);
  return [ref, seen];
}

function Unavailable({ expired, message }: { expired: boolean; message?: string }) {
  return (
    <div className="media-placeholder">
      <ImageOff size={22} aria-hidden="true" />
      {expired
        ? "Ce média n'est plus disponible sur WhatsApp."
        : (message ?? "Média indisponible.")}
    </div>
  );
}

export function MediaContent({
  message,
  onZoom,
}: {
  message: Message;
  onZoom: (url: string) => void;
}) {
  const [ref, seen] = useOnScreen<HTMLDivElement>();
  const media = useMedia(message.id, seen);
  const type = message.type;

  if (type === "document") {
    const name = message.filename ?? "Document";
    return (
      <div ref={ref}>
        {media.status === "ready" ? (
          <a className="file-card" href={media.link.url} target="_blank" rel="noopener noreferrer">
            <FileText size={26} aria-hidden="true" />
            <span style={{ minWidth: 0 }}>
              <span className="file-name">{name}</span>
              <span className="file-sub">Ouvrir le document</span>
            </span>
          </a>
        ) : (
          <div className="file-card">
            <FileText size={26} aria-hidden="true" />
            <span style={{ minWidth: 0 }}>
              <span className="file-name">{name}</span>
              <span className="file-sub">
                {media.status === "loading"
                  ? "Chargement…"
                  : media.status === "expired"
                    ? "Plus disponible sur WhatsApp"
                    : "Indisponible"}
              </span>
            </span>
          </div>
        )}
      </div>
    );
  }

  if (type === "audio") {
    return (
      <div ref={ref} className="media-audio">
        {message.voice && <Mic size={18} aria-label="Message vocal" />}
        {media.status === "ready" ? (
          <audio controls preload="metadata" src={media.link.url} />
        ) : media.status === "loading" ? (
          <span className="file-sub">Chargement de l'audio…</span>
        ) : (
          <span className="file-sub">
            {media.status === "expired"
              ? "Audio plus disponible sur WhatsApp"
              : "Audio indisponible"}
          </span>
        )}
      </div>
    );
  }

  return (
    <div ref={ref} className={`media-frame${type === "sticker" ? " media-sticker" : ""}`}>
      {media.status === "loading" && <div className="media-placeholder">Chargement…</div>}
      {media.status === "expired" && <Unavailable expired />}
      {media.status === "error" && <Unavailable expired={false} message={media.message} />}
      {media.status === "ready" && type === "video" && (
        <video className="media-video" controls preload="metadata" src={media.link.url} />
      )}
      {media.status === "ready" && type !== "video" && (
        <button
          className="media-image"
          onClick={() => onZoom(media.link.url)}
          aria-label="Agrandir la photo"
        >
          <img src={media.link.url} alt="" loading="lazy" />
        </button>
      )}
    </div>
  );
}
