import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const webStore = {
  get(key: string): string | null {
    try {
      return globalThis.localStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    try {
      globalThis.localStorage?.setItem(key, value);
    } catch {
      return;
    }
  },
  remove(key: string): void {
    try {
      globalThis.localStorage?.removeItem(key);
    } catch {
      return;
    }
  },
};

export async function readValue(key: string): Promise<string | null> {
  if (Platform.OS === 'web') return webStore.get(key);
  return SecureStore.getItemAsync(key);
}

export async function writeValue(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') return webStore.set(key, value);
  await SecureStore.setItemAsync(key, value);
}

export async function removeValue(key: string): Promise<void> {
  if (Platform.OS === 'web') return webStore.remove(key);
  await SecureStore.deleteItemAsync(key);
}

export async function readJson<T>(key: string): Promise<T | null> {
  const raw = await readValue(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function writeJson(key: string, value: unknown): Promise<void> {
  await writeValue(key, JSON.stringify(value));
}
