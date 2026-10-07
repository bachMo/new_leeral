import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Easing, View } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { T } from '@/components/T';
import {
  PrimaryButton,
  RoundButton,
  SayBubble,
  ScreenSpeaker,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api, ApiError, asApiError } from '@/lib/api';
import { capture } from '@/lib/capture';
import { POLL_INTERVAL_MS } from '@/lib/config';
import { LANGUAGE_NAMES } from '@/lib/format';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';

type Phase = 'uploading' | 'reading' | 'blurry' | 'failed';

const BLURRY_CODES = new Set([
  'IMAGE_TOO_BLURRY',
  'IMAGE_TOO_DARK',
  'IMAGE_UNREADABLE',
  'DOCUMENT_UNREADABLE',
]);

function ScannedPage() {
  const scan = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scan, {
          toValue: 1,
          duration: 1600,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(scan, {
          toValue: 0,
          duration: 1600,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [scan]);
  const line = (width: number | `${number}%`, height: number, color: string, opacity: number) => ({
    width,
    height,
    borderRadius: height / 2,
    backgroundColor: color,
    opacity,
  });
  return (
    <View
      style={{
        width: 224,
        height: 296,
        borderRadius: 14,
        backgroundColor: colors.sand,
        paddingVertical: 26,
        paddingHorizontal: 22,
        gap: 11,
        overflow: 'hidden',
      }}
    >
      <View style={line('55%', 10, colors.night, 0.55)} />
      <View style={line('35%', 6, colors.night, 0.3)} />
      <View style={{ height: 14 }} />
      <View style={line('100%', 7, colors.night, 0.22)} />
      <View style={line('88%', 7, colors.night, 0.22)} />
      <View style={line('72%', 7, colors.night, 0.22)} />
      <View style={{ height: 10 }} />
      <View style={line('100%', 7, colors.light, 0.9)} />
      <View style={line('64%', 7, colors.light, 0.9)} />
      <View style={{ height: 10 }} />
      <View style={line('80%', 7, colors.night, 0.22)} />
      <View style={line('50%', 7, colors.night, 0.22)} />
      <Animated.View
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 40,
          height: 3,
          backgroundColor: colors.light,
          shadowColor: colors.light,
          shadowOpacity: 0.6,
          shadowRadius: 8,
          transform: [{ translateY: scan.interpolate({ inputRange: [0, 1], outputRange: [0, 210] }) }],
        }}
      />
    </View>
  );
}

function StepRow({ label, state }: { label: string; state: 'done' | 'active' | 'todo' }) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
        padding: 10,
        borderRadius: 14,
        backgroundColor: state === 'active' ? 'rgba(244,166,42,0.12)' : 'transparent',
        opacity: state === 'todo' ? 0.55 : 1,
      }}
    >
      {state === 'done' ? (
        <View
          style={{
            width: 30,
            height: 30,
            borderRadius: 15,
            backgroundColor: colors.river,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="check" size={16} strokeWidth={3} color={colors.white} />
        </View>
      ) : state === 'active' ? (
        <View
          style={{
            width: 30,
            height: 30,
            borderRadius: 15,
            borderWidth: 3,
            borderColor: colors.light,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.light }} />
        </View>
      ) : (
        <View
          style={{
            width: 30,
            height: 30,
            borderRadius: 15,
            borderWidth: 2,
            borderColor: 'rgba(246,240,228,0.4)',
          }}
        />
      )}
      <T w={state === 'active' ? 700 : 400} size={15} color={colors.sand} style={{ flex: 1 }}>
        {label}
      </T>
    </View>
  );
}

function Tip({ icon, label }: { icon: IconName; label: string }) {
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: 'rgba(246,240,228,0.06)',
        borderRadius: 16,
        paddingVertical: 12,
        paddingHorizontal: 8,
        alignItems: 'center',
        gap: 6,
      }}
    >
      <Icon name={icon} size={22} color={colors.light} />
      <T size={13} color={colors.sand} center>
        {label}
      </T>
    </View>
  );
}

export default function ReadingScreen() {
  const { doc } = useLocalSearchParams<{ doc?: string }>();
  const insets = useInsets();
  const { language } = useSession();
  const { say, sayError } = useScreenVoice();
  const [phase, setPhase] = useState<Phase>(doc ? 'reading' : 'uploading');
  const [documentId, setDocumentId] = useState<string | null>(doc ?? null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(Date.now());

  const [files] = useState(() => (doc ? [] : capture.peek()));

  const upload = useCallback(async () => {
    setPhase('uploading');
    setFailure(null);
    started.current = Date.now();
    try {
      const created = await api.uploadDocument(files);
      capture.take();
      setDocumentId(created.id);
      setPhase('reading');
    } catch (error) {
      const failed = asApiError(error);
      setFailure(failed);
      setPhase(BLURRY_CODES.has(failed.code) ? 'blurry' : 'failed');
    }
  }, [files]);

  useEffect(() => {
    if (doc) return;
    if (!files.length) {
      router.replace('/accueil');
      return;
    }
    upload();
  }, [doc, upload]);

  useEffect(() => {
    if (phase !== 'reading' || !documentId) return;
    let alive = true;
    const tick = async () => {
      try {
        const current = await api.document(documentId);
        if (!alive) return;
        if (current.status === 'ready') {
          router.replace(`/explication/${documentId}?fresh=1`);
          return;
        }
        if (current.status === 'unreadable') {
          setPhase('blurry');
          return;
        }
        if (current.status === 'failed') {
          setFailure(
            new ApiError(
              current.failure_reason ?? 'DOCUMENT_UNREADABLE',
              "Je n'ai pas pu lire ce document.",
              0,
              true,
            ),
          );
          setPhase('failed');
          return;
        }
      } catch {
        if (!alive) return;
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };
    let timer = setTimeout(tick, 600);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [phase, documentId]);

  useEffect(() => {
    const interval = setInterval(() => setElapsed((Date.now() - started.current) / 1000), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (phase === 'blurry') say('app.reading.blurry');
    if (phase === 'failed' && failure) sayError(failure);
  }, [phase, failure, say, sayError]);

  const retry = async () => {
    if (!documentId) {
      await upload();
      return;
    }
    try {
      await api.retryDocument(documentId);
      started.current = Date.now();
      setFailure(null);
      setPhase('reading');
    } catch (error) {
      await sayError(error);
    }
  };

  const steps: ('done' | 'active' | 'todo')[] =
    phase === 'uploading'
      ? ['active', 'todo', 'todo']
      : elapsed < 25
        ? ['done', 'active', 'todo']
        : ['done', 'done', 'active'];

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.night,
        paddingTop: insets.top,
        paddingHorizontal: 20,
        paddingBottom: insets.bottom,
        gap: 22,
      }}
    >
      <StatusBar style="light" />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <RoundButton icon="close" label="Annuler" dark onPress={() => router.replace('/accueil')} />
        <T size={14} color={colors.onNightMuted}>
          {phase === 'blurry' || phase === 'failed' ? ' ' : 'Environ 1 minute'}
        </T>
        <ScreenSpeaker prompt={phase === 'blurry' ? 'app.reading.blurry' : 'app.reading.screen'} dark />
      </View>

      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ScannedPage />
      </View>

      {phase === 'uploading' || phase === 'reading' ? (
        <View style={{ gap: 22 }}>
          <View style={{ alignItems: 'center' }}>
            <T display w={700} size={28} ls={-0.6} color={colors.sand} center>
              Je lis ton document…
            </T>
            <T size={15} color={colors.onNightMuted} style={{ marginTop: 4 }}>
              Tu peux poser le téléphone.
            </T>
          </View>
          <View style={{ gap: 4, backgroundColor: 'rgba(246,240,228,0.06)', borderRadius: 22, padding: 8 }}>
            <StepRow label="Lire le document" state={steps[0]} />
            <StepRow label="Comprendre ce qu'il demande" state={steps[1]} />
            <StepRow label={`Te l'expliquer en ${LANGUAGE_NAMES[language].toLowerCase()}`} state={steps[2]} />
          </View>
        </View>
      ) : phase === 'blurry' ? (
        <View style={{ gap: 14 }}>
          <View style={{ alignItems: 'center' }}>
            <T display w={700} size={28} ls={-0.6} color={colors.sand} center>
              Je n&apos;arrive pas à bien lire
            </T>
            <T size={15} color={colors.onNightMuted} center style={{ marginTop: 4 }}>
              {failure?.code === 'IMAGE_TOO_DARK'
                ? 'La photo est trop sombre.'
                : 'La photo est un peu floue ou trop sombre.'}
            </T>
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Tip icon="sun" label="Plus de lumière" />
            <Tip icon="flat" label="Document à plat" />
            <Tip icon="phone" label="Téléphone immobile" />
          </View>
          <PrimaryButton
            label="Reprendre la photo"
            height={64}
            bg={colors.light}
            fg={colors.night}
            onPress={() => router.replace('/camera')}
            left={<Icon name="retry" size={22} color={colors.night} />}
          />
        </View>
      ) : (
        <View style={{ gap: 14 }}>
          <View style={{ alignItems: 'center' }}>
            <T display w={700} size={28} ls={-0.6} color={colors.sand} center>
              Je n&apos;ai pas pu finir
            </T>
            <T size={15} lh={1.4} color={colors.onNightMuted} center style={{ marginTop: 4 }}>
              {failure?.message ?? 'Un problème est survenu. Réessaie.'}
            </T>
          </View>
          <PrimaryButton
            label="Réessayer"
            height={64}
            bg={colors.light}
            fg={colors.night}
            onPress={retry}
            left={<Icon name="retry" size={22} color={colors.night} />}
          />
        </View>
      )}

      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
        <Icon name="lock" size={14} color={colors.onNightMuted} />
        <T size={13} color={colors.onNightMuted}>
          Ton document reste privé.
        </T>
      </View>

      <SayBubble light top={insets.top + 64} />
    </View>
  );
}
