import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { audioBus, enablePlayback } from './audio';

let counter = 0;

export function useClipPlayer(rate = 1) {
  const owner = useRef(`clips-${(counter += 1)}`).current;
  const player = useAudioPlayer(null, { updateInterval: 200, keepAudioSessionActive: true });
  const status = useAudioPlayerStatus(player);
  const [current, setCurrent] = useState<string | null>(null);

  const stop = useCallback(() => {
    try {
      player.pause();
    } catch {
      return;
    }
  }, [player]);

  const play = useCallback(
    async (id: string, url: string | null | undefined) => {
      if (!url || audioBus.recording) return;
      audioBus.claim(owner, stop);
      if (id === current && status.playing) {
        stop();
        return;
      }
      await enablePlayback();
      if (id !== current) {
        player.replace({ uri: url });
        setCurrent(id);
      } else if (status.duration > 0 && status.currentTime >= status.duration - 0.2) {
        await player.seekTo(0);
      }
      player.setPlaybackRate(rate);
      player.play();
    },
    [current, owner, player, rate, status.currentTime, status.duration, status.playing, stop],
  );

  useFocusEffect(
    useCallback(() => {
      return () => stop();
    }, [stop]),
  );

  const isPlaying = (id: string) => current === id && status.playing;
  const progressOf = (id: string) =>
    current === id && status.duration > 0 ? status.currentTime / status.duration : 0;

  return { play, stop, isPlaying, progressOf, current, status };
}
