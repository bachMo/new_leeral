import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { api, ApiError, asApiError } from './api';
import { audioBus, enablePlayback } from './audio';
import { useSession } from './session';
import { readValue, writeValue } from './storage';
import type { Language, Prompt } from './types';

const OWNER = 'guide';
const RATE_KEY = 'leeral.rate';
const PROMPTS_TTL_MS = 40 * 60 * 1000;

export type Speed = 'normal' | 'slow';

type PromptBook = { loadedAt: number; byKey: Map<string, Prompt> };

type VoiceValue = {
  message: string | null;
  speaking: boolean;
  speed: Speed;
  rate: number;
  say: (key: string, language?: Language) => Promise<void>;
  sayText: (text: string, audioUrl?: string | null) => void;
  sayError: (error: unknown) => Promise<void>;
  hush: () => void;
  setSpeed: (speed: Speed) => void;
  playUrl: (url: string | null | undefined) => void;
};

const VoiceContext = createContext<VoiceValue | null>(null);

export function VoiceProvider({ children }: { children: ReactNode }) {
  const { language } = useSession();
  const player = useAudioPlayer(null, { keepAudioSessionActive: true });
  const status = useAudioPlayerStatus(player);
  const [message, setMessage] = useState<string | null>(null);
  const [speed, setSpeedState] = useState<Speed>('normal');
  const books = useRef(new Map<Language, PromptBook>());
  const rate = speed === 'slow' ? 0.8 : 1;

  useEffect(() => {
    readValue(RATE_KEY).then((stored) => {
      if (stored === 'slow' || stored === 'normal') setSpeedState(stored);
    });
  }, []);

  const book = useCallback(async (lang: Language, force = false) => {
    const cached = books.current.get(lang);
    if (cached && !force && Date.now() - cached.loadedAt < PROMPTS_TTL_MS) return cached;
    try {
      const prompts = await api.prompts(lang);
      const fresh = { loadedAt: Date.now(), byKey: new Map(prompts.map((prompt) => [prompt.key, prompt])) };
      books.current.set(lang, fresh);
      return fresh;
    } catch {
      return cached ?? null;
    }
  }, []);

  useEffect(() => {
    book(language);
  }, [book, language]);

  const heard = useRef(false);

  useEffect(() => {
    if (!message) return;
    if (status.playing) {
      heard.current = true;
      return;
    }
    const delay = heard.current ? 3500 : Math.max(6000, message.length * 70);
    const timer = setTimeout(() => setMessage(null), delay);
    return () => clearTimeout(timer);
  }, [message, status.playing]);

  const stop = useCallback(() => {
    try {
      player.pause();
    } catch {
      return;
    }
  }, [player]);

  const playUrl = useCallback(
    (url: string | null | undefined) => {
      if (!url || audioBus.recording) return;
      audioBus.claim(OWNER, stop);
      enablePlayback().then(() => {
        try {
          player.replace({ uri: url });
          player.setPlaybackRate(rate);
          player.play();
        } catch {
          return;
        }
      });
    },
    [player, rate, stop],
  );

  const sayText = useCallback(
    (text: string, audioUrl?: string | null) => {
      heard.current = false;
      setMessage(text);
      if (audioUrl) playUrl(audioUrl);
      else stop();
    },
    [playUrl, stop],
  );

  const say = useCallback(
    async (key: string, lang?: Language) => {
      const target = lang ?? language;
      const current = await book(target);
      const prompt = current?.byKey.get(key);
      if (!prompt) return;
      sayText(prompt.text_fr, prompt.audio_url);
    },
    [book, language, sayText],
  );

  const sayError = useCallback(
    async (error: unknown) => {
      const failure = asApiError(error);
      const current = await book(language);
      const prompt = failure instanceof ApiError ? current?.byKey.get(failure.promptKey) : undefined;
      if (prompt) sayText(failure.message || prompt.text_fr, prompt.audio_url);
      else sayText(failure.message);
    },
    [book, language, sayText],
  );

  const hush = useCallback(() => {
    setMessage(null);
    stop();
  }, [stop]);

  const setSpeed = useCallback((next: Speed) => {
    setSpeedState(next);
    writeValue(RATE_KEY, next);
  }, []);

  const value = useMemo<VoiceValue>(
    () => ({
      message,
      speaking: status.playing,
      speed,
      rate,
      say,
      sayText,
      sayError,
      hush,
      setSpeed,
      playUrl,
    }),
    [message, status.playing, speed, rate, say, sayText, sayError, hush, setSpeed, playUrl],
  );

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
}

export function useVoice(): VoiceValue {
  const value = useContext(VoiceContext);
  if (!value) throw new Error('VoiceProvider is missing');
  return value;
}
