import { randomUUID } from 'expo-crypto';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, clearSession, loadSession, onSessionChange, saveTokens } from './api';
import { readValue, writeValue } from './storage';
import type { Language, Me, Tokens } from './types';

const DEVICE_KEY = 'leeral.device';
const LANGUAGE_KEY = 'leeral.language';

type SessionValue = {
  ready: boolean;
  offline: boolean;
  me: Me | null;
  language: Language;
  isGuest: boolean;
  chooseLanguage: (language: Language) => Promise<void>;
  applyTokens: (tokens: Tokens) => Promise<Me>;
  refreshMe: () => Promise<Me | null>;
  logout: () => Promise<void>;
};

const SessionContext = createContext<SessionValue | null>(null);

async function deviceId(): Promise<string> {
  const stored = await readValue(DEVICE_KEY);
  if (stored) return stored;
  const created = randomUUID().replace(/-/g, '');
  await writeValue(DEVICE_KEY, created);
  return created;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [stored, setStored] = useState(false);
  const [language, setLanguage] = useState<Language>('wo');

  const refreshMe = useCallback(async () => {
    try {
      const current = await api.me();
      setMe(current);
      setLanguage(current.user.language);
      return current;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    onSessionChange((tokens) => {
      if (!tokens) {
        setMe(null);
        setStored(false);
      }
    });
    (async () => {
      const storedLanguage = (await readValue(LANGUAGE_KEY)) as Language | null;
      if (storedLanguage) setLanguage(storedLanguage);
      if (await loadSession()) {
        setStored(true);
        await refreshMe();
      }
      setReady(true);
    })();
  }, [refreshMe]);

  const startGuest = useCallback(
    async (chosen: Language) => {
      const tokens = await api.startGuest(await deviceId(), chosen);
      await saveTokens(tokens);
      await refreshMe();
      setStored(true);
    },
    [refreshMe],
  );

  const chooseLanguage = useCallback(
    async (chosen: Language) => {
      await writeValue(LANGUAGE_KEY, chosen);
      setLanguage(chosen);
      if (me) {
        setMe(await api.updateMe({ language: chosen }));
      } else {
        await startGuest(chosen);
      }
    },
    [me, startGuest],
  );

  const applyTokens = useCallback(async (tokens: Tokens) => {
    await saveTokens(tokens);
    const current = await api.me();
    setMe(current);
    setStored(true);
    setLanguage(current.user.language);
    return current;
  }, []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    await clearSession();
    setStored(false);
    try {
      await startGuest(language);
    } catch {
      setMe(null);
    }
  }, [language, startGuest]);

  const value = useMemo<SessionValue>(
    () => ({
      ready,
      offline: ready && stored && !me,
      me,
      language,
      isGuest: me?.user.is_guest ?? true,
      chooseLanguage,
      applyTokens,
      refreshMe,
      logout,
    }),
    [ready, stored, me, language, chooseLanguage, applyTokens, refreshMe, logout],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('SessionProvider is missing');
  return value;
}
