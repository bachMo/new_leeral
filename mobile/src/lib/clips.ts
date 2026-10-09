import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';

import { audioBus, enablePlayback, untilLoaded } from './audio';

let counter = 0;

type PendingSeek = { id: string; fraction: number };

export function useClipPlayer(rate = 1) {
  const owner = useRef(`clips-${(counter += 1)}`).current;
  const player = useAudioPlayer(null, { updateInterval: 200, keepAudioSessionActive: true });
  const status = useAudioPlayerStatus(player);
  const [current, setCurrent] = useState<string | null>(null);
  const pendingSeek = useRef<PendingSeek | null>(null);

  const stop = useCallback(() => {
    try {
      player.pause();
    } catch {
      return;
    }
  }, [player]);

  const load = useCallback(
    async (id: string, url: string) => {
      audioBus.claim(owner, stop);
      await enablePlayback();
      if (id !== current) {
        player.replace({ uri: url });
        setCurrent(id);
        await untilLoaded(player);
      }
      player.setPlaybackRate(rate);
    },
    [current, owner, player, rate, stop],
  );

  const play = useCallback(
    async (id: string, url: string | null | undefined) => {
      if (!url || audioBus.recording) return;
      if (id === current && status.playing) {
        stop();
        return;
      }
      const finished = status.duration > 0 && status.currentTime >= status.duration - 0.2;
      await load(id, url);
      if (id === current && finished) await player.seekTo(0);
      player.play();
    },
    [current, load, player, status.currentTime, status.duration, status.playing, stop],
  );

  const seek = useCallback(
    async (id: string, url: string | null | undefined, fraction: number) => {
      if (!url || audioBus.recording) return;
      if (id === current && status.duration > 0) {
        await player.seekTo(fraction * status.duration);
        return;
      }
      pendingSeek.current = { id, fraction };
      await load(id, url);
      player.play();
    },
    [current, load, player, status.duration],
  );

  useEffect(() => {
    const pending = pendingSeek.current;
    if (!pending || pending.id !== current || status.duration <= 0) return;
    pendingSeek.current = null;
    player.seekTo(pending.fraction * status.duration);
  }, [current, player, status.duration]);

  useFocusEffect(
    useCallback(() => {
      return () => stop();
    }, [stop]),
  );

  const isPlaying = (id: string) => current === id && status.playing;
  const progressOf = (id: string) =>
    current === id && status.duration > 0 ? status.currentTime / status.duration : 0;

  return { play, seek, stop, isPlaying, progressOf, current, status };
}
