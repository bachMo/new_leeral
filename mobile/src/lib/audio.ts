import { AudioModule, setAudioModeAsync } from 'expo-audio';

type Stopper = () => void;

const owners = new Map<string, Stopper>();
let recording = false;

export const audioBus = {
  claim(owner: string, stop: Stopper): void {
    for (const [name, stopper] of owners) {
      if (name !== owner) {
        try {
          stopper();
        } catch {
          continue;
        }
      }
    }
    owners.set(owner, stop);
  },
  release(owner: string): void {
    owners.delete(owner);
  },
  get recording(): boolean {
    return recording;
  },
  setRecording(active: boolean): void {
    recording = active;
  },
  stopAll(): void {
    for (const stopper of owners.values()) {
      try {
        stopper();
      } catch {
        continue;
      }
    }
  },
};

export async function enablePlayback(): Promise<void> {
  if (recording) return;
  try {
    await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
  } catch {
    return;
  }
}

export async function enableRecording(): Promise<boolean> {
  const permission = await AudioModule.requestRecordingPermissionsAsync();
  if (!permission.granted) return false;
  await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
  return true;
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}
