import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Platform, ScrollView, View } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  Loading,
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { useClipPlayer } from '@/lib/clips';
import { useSession } from '@/lib/session';
import { openPdf, sharePdf } from '@/lib/share';
import { colors } from '@/lib/theme';
import type { Writing, WritingOutput } from '@/lib/types';

const KIND_ORDER: WritingOutput['kind'][] = ['cv', 'cover_letter', 'letter'];
const KIND_LABEL: Record<WritingOutput['kind'], string> = {
  cv: 'CV',
  cover_letter: 'Lettre de motivation',
  letter: 'Lettre',
};

function latestOutputs(writing: Writing): WritingOutput[] {
  const byKind = new Map<WritingOutput['kind'], WritingOutput>();
  for (const output of writing.outputs) {
    const current = byKind.get(output.kind);
    if (!current || output.version > current.version) byKind.set(output.kind, output);
  }
  return KIND_ORDER.flatMap((kind) => (byKind.has(kind) ? [byKind.get(kind) as WritingOutput] : []));
}

function Paper({ output }: { output: WritingOutput }) {
  const blocks = output.content
    .split(/\n\s*\n/)
    .map((block) => block.split('\n').filter((line) => line.trim()));
  const [title, ...rest] = blocks;
  return (
    <View style={{ gap: 9 }}>
      <T display w={800} size={17} ls={-0.3}>
        {title?.join(' ')}
      </T>
      <View style={{ height: 1, backgroundColor: colors.line }} />
      {rest.map((lines, index) => {
        const heading =
          lines.length > 1 && lines[0].length <= 40 && !/[.,:;]$/.test(lines[0]) ? lines[0] : null;
        const body = heading ? lines.slice(1) : lines;
        return (
          <View key={index} style={{ gap: 3 }}>
            {heading ? (
              <T w={800} size={8.5} ls={1} upper>
                {heading}
              </T>
            ) : null}
            {body.map((line, lineIndex) => (
              <T key={lineIndex} size={9.5} lh={1.45} color={colors.docInk}>
                {line}
              </T>
            ))}
          </View>
        );
      })}
    </View>
  );
}

function Action({
  icon,
  label,
  prompt,
  busy,
  onPress,
}: {
  icon: IconName;
  label: string;
  prompt: string;
  busy?: boolean;
  onPress: () => void;
}) {
  return (
    <View style={{ flex: 1 }}>
      <Tap
        accessibilityRole="button"
        accessibilityLabel={label}
        onPress={onPress}
        disabled={busy}
        style={{
          height: 72,
          borderRadius: 18,
          backgroundColor: colors.paper,
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
        }}
      >
        {busy ? <ActivityIndicator color={colors.night} /> : <Icon name={icon} size={22} />}
        <T w={700} size={13}>
          {label}
        </T>
      </Tap>
      <MiniSpeaker
        prompt={prompt}
        label={`Écouter : ${label}`}
        width={36}
        height={36}
        opacity={0.5}
        style={{ position: 'absolute', top: 2, right: 2 }}
      />
    </View>
  );
}

export default function WritingReadyScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useInsets();
  const { me, refreshMe } = useSession();
  const { sayError, rate } = useScreenVoice();
  const clips = useClipPlayer(rate);
  const [writing, setWriting] = useState<Writing | null>(null);
  const [tab, setTab] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.writing(id).then(setWriting).catch(sayError);
    refreshMe();
  }, [id, refreshMe, sayError]);

  const outputs = useMemo(() => (writing ? latestOutputs(writing) : []), [writing]);
  const readback = outputs.find((output) => output.readback_audio_url);

  if (!writing) return <Loading />;
  const current = outputs[Math.min(tab, outputs.length - 1)];
  const filename = current ? `leeral-${current.kind}.pdf` : 'leeral.pdf';

  const send = async () => {
    if (!current) return;
    setBusy('send');
    try {
      await sharePdf(current.pdf_url, filename);
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(null);
    }
  };

  const download = async () => {
    if (!current) return;
    setBusy('download');
    try {
      await openPdf(current.pdf_url);
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(null);
    }
  };

  const restart = async () => {
    setBusy('edit');
    try {
      const fresh = await api.startWriting(writing.type);
      router.replace(`/ecrit/${fresh.id}`);
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(null);
    }
  };

  const edit = () => {
    if (Platform.OS === 'web') {
      restart();
      return;
    }
    Alert.alert(
      'Refaire le document ?',
      'Je te repose les questions. Cela compte comme un nouveau document ce mois-ci.',
      [
        { text: 'Non', style: 'cancel' },
        { text: 'Oui, refaire', onPress: restart },
      ],
    );
  };

  const usage = me?.usage;
  const plus = me?.plan.code === 'leeral_plus';
  const subtitle =
    outputs.length > 1
      ? 'Ton CV et ta lettre en français'
      : `Ta ${KIND_LABEL[current?.kind ?? 'letter'].toLowerCase()} en français`;

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.sand,
        paddingTop: insets.top,
        paddingHorizontal: 20,
        paddingBottom: insets.bottom,
        gap: 14,
      }}
    >
      <StatusBar style="dark" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <BackButton />
        <View style={{ flex: 1 }}>
          <T display w={700} size={24} lh={1.05}>
            C&apos;est prêt !
          </T>
          <T size={13} color={colors.muted}>
            {subtitle}
          </T>
        </View>
        <ScreenSpeaker prompt="app.writing_ready.screen" />
      </View>

      {outputs.length > 1 ? (
        <View
          style={{
            flexDirection: 'row',
            gap: 4,
            backgroundColor: colors.sandDark,
            borderRadius: 16,
            padding: 4,
          }}
        >
          {outputs.map((output, index) => (
            <Tap
              key={output.id}
              accessibilityRole="button"
              accessibilityState={{ selected: index === tab }}
              onPress={() => setTab(index)}
              style={{
                flex: 1,
                height: 40,
                borderRadius: 12,
                backgroundColor: index === tab ? colors.paper : 'transparent',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <T w={700} size={14}>
                {KIND_LABEL[output.kind]}
              </T>
            </Tap>
          ))}
        </View>
      ) : null}

      <View style={{ flex: 1, minHeight: 0, alignItems: 'center' }}>
        <ScrollView
          style={{
            width: 286,
            maxHeight: 360,
            backgroundColor: colors.white,
            borderRadius: 6,
            borderWidth: 1,
            borderColor: colors.line,
            shadowColor: colors.night,
            shadowOpacity: 0.14,
            shadowRadius: 15,
            shadowOffset: { width: 0, height: 10 },
            elevation: 6,
          }}
          contentContainerStyle={{ padding: 22 }}
        >
          {current ? <Paper output={current} /> : <T size={13}>Le document arrive…</T>}
        </ScrollView>
      </View>

      <View>
        <Tap
          accessibilityRole="button"
          disabled={!readback}
          onPress={() => readback && clips.play(readback.id, readback.readback_audio_url)}
          style={{
            height: 64,
            borderRadius: 22,
            backgroundColor: colors.night,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 12,
            paddingHorizontal: 10,
          }}
        >
          <View
            style={{
              width: 46,
              height: 46,
              borderRadius: 23,
              backgroundColor: colors.light,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon
              name={readback && clips.isPlaying(readback.id) ? 'pause' : 'play'}
              size={18}
              color={colors.night}
            />
          </View>
          <View>
            <T display w={700} size={17} color={colors.sand}>
              Écouter ce que j&apos;ai écrit
            </T>
            <T size={13} color={colors.onNightMuted}>
              {readback ? 'Lu dans ta langue, pour vérifier' : 'La lecture n’est pas encore prête'}
            </T>
          </View>
        </Tap>
        <MiniSpeaker
          prompt="app.writing_ready.listen"
          label="Écouter : vérifier le document"
          color={colors.sand}
          style={{ position: 'absolute', right: 6, top: 12 }}
        />
      </View>

      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Action
          icon="share"
          label="Envoyer"
          prompt="app.writing_ready.send"
          busy={busy === 'send'}
          onPress={send}
        />
        <Action
          icon="download"
          label="Télécharger"
          prompt="app.writing_ready.download"
          busy={busy === 'download'}
          onPress={download}
        />
        <Action
          icon="penBare"
          label="Modifier"
          prompt="app.writing_ready.edit"
          busy={busy === 'edit'}
          onPress={edit}
        />
      </View>

      {usage ? (
        <T size={13} color={colors.muted} center>
          {Math.min(usage.writings_used, usage.writings_limit)} document{usage.writings_used > 1 ? 's' : ''}{' '}
          sur {usage.writings_limit} ce mois
          {plus ? null : (
            <>
              {' · '}
              <T
                w={700}
                size={13}
                style={{ textDecorationLine: 'underline' }}
                onPress={() => router.push('/plus')}
              >
                Passer à Leeral+
              </T>
            </>
          )}
        </T>
      ) : null}

      <SayBubble top={insets.top + 64} />
    </View>
  );
}
