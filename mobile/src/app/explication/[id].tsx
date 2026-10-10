import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, View } from 'react-native';

import { KeepSheet } from '@/components/KeepSheet';
import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  Halo,
  Loading,
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  Waveform,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { audioBus, enablePlayback, formatDuration, untilLoaded } from '@/lib/audio';
import { POLL_INTERVAL_MS } from '@/lib/config';
import { plural, shortDate } from '@/lib/format';
import { useSession } from '@/lib/session';
import { categoryStyle, colors } from '@/lib/theme';
import type { DocumentDetail, Explanation } from '@/lib/types';

const OWNER = 'explanation';
const BARS = [10, 18, 26, 14, 30, 36, 22, 12, 28, 34, 20, 16, 32, 24, 12, 20, 30, 18, 10, 24, 16, 12];

function ControlButton({
  label,
  onPress,
  prompt,
  active,
  busy,
}: {
  label: string;
  onPress: () => void;
  prompt: string;
  active?: boolean;
  busy?: boolean;
}) {
  return (
    <View style={{ flexGrow: 1, flexBasis: 130 }}>
      <Tap
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ selected: !!active, busy: !!busy }}
        onPress={onPress}
        disabled={busy}
        style={{
          height: 46,
          borderRadius: 14,
          backgroundColor: active ? 'rgba(244,166,42,0.24)' : 'rgba(246,240,228,0.08)',
          flexDirection: 'row',
          alignItems: 'center',
          paddingLeft: 12,
          paddingRight: 40,
          gap: 6,
        }}
      >
        <T w={600} size={14} color={colors.sand} numberOfLines={1} style={{ flexShrink: 1 }}>
          {label}
        </T>
        {busy ? <ActivityIndicator size="small" color={colors.light} /> : null}
      </Tap>
      <MiniSpeaker
        prompt={prompt}
        label={`Écouter : ${label.toLowerCase()}`}
        color={colors.sand}
        style={{ position: 'absolute', right: 2, top: 3 }}
      />
    </View>
  );
}

export default function ExplanationScreen() {
  const { id, fresh } = useLocalSearchParams<{ id: string; fresh?: string }>();
  const insets = useInsets();
  const { isGuest } = useSession();
  const { sayText, sayError, speed } = useScreenVoice();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [variant, setVariant] = useState<'standard' | 'simple'>('standard');
  const [slow, setSlow] = useState(speed === 'slow');
  const [simplifying, setSimplifying] = useState(false);
  const [opening, setOpening] = useState(false);
  const [keepOpen, setKeepOpen] = useState(false);
  const keepShown = useRef(false);
  const loadedUrl = useRef<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const player = useAudioPlayer(null, { updateInterval: 250, keepAudioSessionActive: true });
  const status = useAudioPlayerStatus(player);

  const explanation: Explanation | null = doc
    ? variant === 'simple'
      ? doc.simple_explanation
      : doc.explanation
    : null;
  const rate = slow ? 0.8 : 1;

  useEffect(() => {
    api.document(id).then(setDoc).catch(sayError);
  }, [id, sayError]);

  const seek = useCallback(
    async (fraction: number) => {
      const total = status.duration > 0 ? status.duration : (explanation?.audio_duration_s ?? 0);
      if (!total) return;
      await player.seekTo(fraction * total);
    },
    [explanation?.audio_duration_s, player, status.duration],
  );

  const pause = useCallback(() => {
    try {
      player.pause();
    } catch {
      return;
    }
  }, [player]);

  const play = useCallback(
    async (fromStart = false) => {
      audioBus.claim(OWNER, pause);
      await enablePlayback();
      if (
        fromStart ||
        status.didJustFinish ||
        (status.duration > 0 && status.currentTime >= status.duration - 0.2)
      ) {
        await player.seekTo(0);
      }
      player.setPlaybackRate(rate);
      player.play();
    },
    [pause, player, rate, status.currentTime, status.didJustFinish, status.duration],
  );

  useEffect(() => {
    const url = explanation?.audio_url;
    if (!url || loadedUrl.current === explanation?.id) return;
    loadedUrl.current = explanation.id;
    player.replace({ uri: url });
    audioBus.claim(OWNER, pause);
    enablePlayback()
      .then(() => untilLoaded(player))
      .then(() => {
        player.setPlaybackRate(rate);
        player.play();
      });
  }, [explanation, pause, player, rate]);

  useEffect(() => {
    player.setPlaybackRate(rate);
  }, [player, rate]);

  useFocusEffect(
    useCallback(() => {
      return () => pause();
    }, [pause]),
  );

  useEffect(() => {
    if (status.didJustFinish && isGuest && fresh && !keepShown.current) {
      keepShown.current = true;
      setKeepOpen(true);
    }
  }, [status.didJustFinish, isGuest, fresh]);

  const simplify = async () => {
    if (!doc) return;
    if (doc.simple_explanation) {
      setVariant('simple');
      return;
    }
    setSimplifying(true);
    try {
      await api.simplify(doc.id);
      for (let attempt = 0; attempt < 60 && mounted.current; attempt += 1) {
        const current = await api.document(doc.id);
        if (current.simple_explanation) {
          if (!mounted.current) return;
          setDoc(current);
          setVariant('simple');
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      if (mounted.current)
        sayText("Je n'ai pas encore pu préparer l'explication plus simple. Réessaie dans un instant.");
    } catch (error) {
      await sayError(error);
    } finally {
      setSimplifying(false);
    }
  };

  const ask = async () => {
    if (!doc) return;
    setOpening(true);
    try {
      const conversation = await api.openConversation(doc.id);
      pause();
      router.push(`/conversation/${conversation.id}?doc=${doc.id}`);
    } catch (error) {
      await sayError(error);
    } finally {
      setOpening(false);
    }
  };

  if (!doc) return <Loading />;

  const category = categoryStyle[doc.category] ?? categoryStyle.other;
  const meta = [
    doc.issuer,
    doc.document_date ? shortDate(doc.document_date) : null,
    plural(doc.page_count, 'page'),
  ]
    .filter(Boolean)
    .join(' · ');
  const duration = status.duration > 0 ? status.duration : (explanation?.audio_duration_s ?? 0);
  const playing = status.playing;

  return (
    <View style={{ flex: 1, backgroundColor: colors.sand }}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top, paddingHorizontal: 20, paddingBottom: 16, gap: 14 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <BackButton />
          <View style={{ flex: 1 }}>
            <T display w={700} size={22} lh={1.1} numberOfLines={2}>
              {doc.title ?? 'Document'}
            </T>
            <T size={13} color={colors.muted} numberOfLines={1}>
              {meta}
            </T>
          </View>
          <ScreenSpeaker prompt="app.explanation.screen" />
        </View>

        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {doc.urgency !== 'none' && doc.urgency_label ? (
            <View
              style={{
                height: 32,
                paddingHorizontal: 12,
                borderRadius: 16,
                backgroundColor: doc.urgency === 'urgent' ? colors.claySoft : colors.lightSoft,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Icon
                name={doc.urgency === 'urgent' ? 'alert' : 'clock'}
                size={14}
                color={doc.urgency === 'urgent' ? colors.clayInk : colors.lightInk}
              />
              <T w={700} size={13.5} color={doc.urgency === 'urgent' ? colors.clayInk : colors.lightInk}>
                {doc.urgency_label}
              </T>
            </View>
          ) : null}
          <View
            style={{
              height: 32,
              paddingHorizontal: 12,
              borderRadius: 16,
              backgroundColor: colors.paper,
              borderWidth: 1,
              borderColor: colors.line,
              justifyContent: 'center',
            }}
          >
            <T w={600} size={13.5}>
              {category.label}
            </T>
          </View>
        </View>

        <View style={{ backgroundColor: colors.night, borderRadius: 28, padding: 20, gap: 16 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
            <Tap
              accessibilityRole="button"
              accessibilityLabel={playing ? 'Mettre en pause' : "Écouter l'explication"}
              onPress={() => (playing ? pause() : play())}
              disabled={!explanation}
            >
              <Halo size={96} inset={11} core={60} outer={0.14} middle={0.24}>
                {!explanation ? (
                  <ActivityIndicator color={colors.night} />
                ) : (
                  <Icon name={playing ? 'pause' : 'play'} size={24} color={colors.night} />
                )}
              </Halo>
            </Tap>
            <View style={{ flex: 1, minWidth: 0, gap: 8 }}>
              <Waveform
                bars={BARS}
                progress={duration ? status.currentTime / duration : 0}
                onSeek={seek}
                label="Avancer ou reculer dans l'explication"
                active={colors.light}
                inactive="rgba(246,240,228,0.28)"
              />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <T size={13} color={colors.onNightMuted} style={{ fontVariant: ['tabular-nums'] }}>
                  {formatDuration(status.currentTime)}
                </T>
                <T size={13} color={colors.onNightMuted} style={{ fontVariant: ['tabular-nums'] }}>
                  {formatDuration(duration)}
                </T>
              </View>
            </View>
          </View>
          {explanation ? (
            <T size={16} lh={1.45} color={colors.sand} numberOfLines={5}>
              « {explanation.text_fr} »
            </T>
          ) : (
            <T size={16} lh={1.45} color={colors.onNightMuted}>
              L&apos;explication arrive…
            </T>
          )}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            <ControlButton label="Répéter" prompt="app.explanation.repeat" onPress={() => play(true)} />
            <ControlButton
              label="Plus lent"
              prompt="app.explanation.slower"
              active={slow}
              onPress={() => setSlow((value) => !value)}
            />
            <ControlButton
              label="Plus simple"
              prompt="app.explanation.simpler"
              active={variant === 'simple'}
              busy={simplifying}
              onPress={() => (variant === 'simple' ? setVariant('standard') : simplify())}
            />
          </View>
        </View>

        {doc.key_points.length ? (
          <View style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <T display w={700} size={18} style={{ flex: 1 }}>
                Ce que tu dois faire
              </T>
              <MiniSpeaker prompt="app.explanation.todo" label="Écouter : ce que tu dois faire" />
            </View>
            {doc.key_points.map((point) => (
              <View
                key={point.position}
                style={{
                  backgroundColor: colors.paper,
                  borderRadius: 18,
                  paddingVertical: 8,
                  paddingRight: 8,
                  paddingLeft: 12,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <View
                  style={{
                    minWidth: 40,
                    maxWidth: 104,
                    height: 40,
                    paddingHorizontal: 6,
                    borderRadius: 12,
                    backgroundColor: colors.lightSoft,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <T
                    display
                    w={800}
                    size={point.tag.length > 4 ? 13 : 15}
                    color={colors.lightInk}
                    numberOfLines={1}
                    adjustsFontSizeToFit
                  >
                    {point.tag || '•'}
                  </T>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <T w={700} size={15.5}>
                    {point.title_fr}
                  </T>
                  {point.detail_fr ? (
                    <T size={13} color={colors.muted}>
                      {point.detail_fr}
                    </T>
                  ) : null}
                </View>
                <MiniSpeaker
                  label="Écouter ce point"
                  width={40}
                  height={44}
                  onPress={() => {
                    pause();
                    sayText([point.title_fr, point.detail_fr].filter(Boolean).join(' · '), point.audio_url);
                  }}
                />
              </View>
            ))}
          </View>
        ) : null}
      </ScrollView>

      <View
        style={{
          paddingTop: 12,
          paddingHorizontal: 20,
          paddingBottom: insets.bottom,
          backgroundColor: colors.sand,
          borderTopWidth: 1,
          borderTopColor: colors.line,
        }}
      >
        <Tap
          accessibilityRole="button"
          accessibilityLabel="Poser une question"
          onPress={ask}
          disabled={opening}
          style={{
            height: 68,
            borderRadius: 34,
            backgroundColor: colors.night,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 14,
            paddingHorizontal: 8,
          }}
        >
          <View
            style={{
              width: 44,
              height: 44,
              borderRadius: 22,
              backgroundColor: colors.paper,
              borderWidth: 1,
              borderColor: colors.line,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {opening ? <ActivityIndicator color={colors.night} /> : <Icon name="mic" size={24} />}
          </View>
          <View>
            <T display w={700} size={18} color={colors.sand}>
              Poser une question
            </T>
            <T size={13} color={colors.onNightMuted}>
              Sur ce document, à voix haute
            </T>
          </View>
        </Tap>
        <MiniSpeaker
          prompt="app.explanation.question"
          label="Écouter : poser une question"
          color={colors.sand}
          width={44}
          height={44}
          style={{ position: 'absolute', top: 24, right: 30 }}
        />
      </View>

      <SayBubble bottom={116 + Math.max(insets.bottom - 26, 0)} />
      <KeepSheet
        visible={keepOpen}
        title={doc.title ?? 'Document'}
        onKeep={() => {
          setKeepOpen(false);
          pause();
          router.push(`/numero?next=${encodeURIComponent(`/explication/${doc.id}`)}`);
        }}
        onDismiss={() => setKeepOpen(false)}
      />
    </View>
  );
}
