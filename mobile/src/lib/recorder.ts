import { RecordingPresets, useAudioRecorder } from 'expo-audio';
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { Platform } from 'react-native';

import { audioBus, enablePlayback, enableRecording } from './audio';
import type { LocalFile } from './types';

const MIN_DURATION_MS = 700;

export type RecorderState = 'idle' | 'recording';

export function useVoiceRecorder() {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [state, setState] = useState<RecorderState>('idle');
  const [denied, setDenied] = useState(false);
  const startedAt = useRef(0);
  const active = useRef(false);
  const starting = useRef(false);

  const finish = useCallback(async () => {
    active.current = false;
    audioBus.setRecording(false);
    setState('idle');
    await enablePlayback();
  }, []);

  const start = useCallback(async () => {
    if (starting.current || active.current) return false;
    starting.current = true;
    try {
      audioBus.stopAll();
      if (!(await enableRecording())) {
        setDenied(true);
        return false;
      }
      setDenied(false);
      audioBus.setRecording(true);
      await recorder.prepareToRecordAsync();
      recorder.record();
      startedAt.current = Date.now();
      active.current = true;
      setState('recording');
      return true;
    } catch {
      await finish();
      return false;
    } finally {
      starting.current = false;
    }
  }, [finish, recorder]);

  const stop = useCallback(async (): Promise<LocalFile | null> => {
    if (!active.current) return null;
    try {
      await recorder.stop();
    } finally {
      await finish();
    }
    const uri = recorder.uri;
    if (!uri || Date.now() - startedAt.current < MIN_DURATION_MS) return null;
    if (Platform.OS === 'web') return { uri, name: 'voice.webm', type: 'audio/webm' };
    return { uri, name: 'voice.m4a', type: 'audio/mp4' };
  }, [finish, recorder]);

  const cancel = useCallback(async () => {
    if (!active.current) return;
    try {
      await recorder.stop();
    } finally {
      await finish();
    }
  }, [finish, recorder]);

  useFocusEffect(
    useCallback(() => {
      return () => {
        cancel();
      };
    }, [cancel]),
  );

  return { state, recording: state === 'recording', denied, start, stop, cancel };
}
