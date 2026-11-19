import { useEffect, useRef, useState } from "react";
import { ApiError, mediaLink } from "./api";
import type { MediaLink } from "./types";

export function useInterval(callback: () => void, delay: number | null): void {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    if (delay === null) return;
    const id = window.setInterval(() => saved.current(), delay);
    return () => window.clearInterval(id);
  }, [delay]);
}

export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");
  useEffect(() => {
    const update = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return visible;
}

export function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useInterval(() => setNow(Date.now()), intervalMs);
  return now;
}

const MEDIA_TTL = 45 * 60 * 1000;
const mediaCache = new Map<string, { link: MediaLink; at: number }>();
const mediaRequests = new Map<string, Promise<MediaLink>>();

function loadMedia(messageId: string): Promise<MediaLink> {
  const cached = mediaCache.get(messageId);
  if (cached && Date.now() - cached.at < MEDIA_TTL) return Promise.resolve(cached.link);
  const pending = mediaRequests.get(messageId);
  if (pending) return pending;
  const promise = mediaLink(messageId)
    .then((link) => {
      mediaCache.set(messageId, { link, at: Date.now() });
      return link;
    })
    .finally(() => mediaRequests.delete(messageId));
  mediaRequests.set(messageId, promise);
  return promise;
}

export type MediaState =
  | { status: "loading" }
  | { status: "ready"; link: MediaLink }
  | { status: "expired" }
  | { status: "error"; message: string };

export function useMedia(messageId: string, enabled = true): MediaState {
  const [state, setState] = useState<MediaState>({ status: "loading" });
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    loadMedia(messageId)
      .then((link) => active && setState({ status: "ready", link }))
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 410) setState({ status: "expired" });
        else
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Média indisponible.",
          });
      });
    return () => {
      active = false;
    };
  }, [messageId, enabled]);
  return state;
}
