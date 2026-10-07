import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { LiveBars, MicButton } from '@/components/Mic';
import { T } from '@/components/T';
import { TextAnswer } from '@/components/TextAnswer';
import {
  BackButton,
  Loading,
  MiniSpeaker,
  PrimaryButton,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { barsFor, VoiceNote } from '@/components/VoiceNote';
import { api } from '@/lib/api';
import { useClipPlayer } from '@/lib/clips';
import { POLL_INTERVAL_MS } from '@/lib/config';
import { useVoiceRecorder } from '@/lib/recorder';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { LocalFile, Message, TextLanguage, Writing } from '@/lib/types';

type Answer = { audio?: LocalFile; text?: string };

export default function WritingScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useInsets();
  const { language, refreshMe } = useSession();
  const { say, sayText, sayError, rate } = useScreenVoice();
  const clips = useClipPlayer(rate);
  const recorder = useVoiceRecorder();
  const [writing, setWriting] = useState<Writing | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [replyId, setReplyId] = useState<string | null>(null);
  const [unclear, setUnclear] = useState(false);
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(false);
  const playedQuestion = useRef<string | null>(null);
  const playClip = useRef(clips.play);
  playClip.current = clips.play;

  const load = useCallback(async () => {
    const current = await api.writing(id);
    setWriting(current);
    const list = await api.messages(current.conversation_id);
    setMessages(list);
    return { current, list };
  }, [id]);

  useEffect(() => {
    load().catch(sayError);
  }, [load, sayError]);

  const step = writing && writing.status === 'collecting' ? writing.steps[writing.current_step] : undefined;
  const question = step ? messages.find((message) => message.id === step.question_message_id) : undefined;
  const reply = replyId ? messages.find((message) => message.id === replyId) : undefined;
  const waitingQuestion = !!step && (!question || question.status === 'pending');
  const waitingReply = !!replyId && (!reply || reply.status === 'pending');

  useEffect(() => {
    if (writing?.status === 'ready') router.replace(`/ecrit-pret/${writing.id}`);
  }, [writing]);

  const status = writing?.status;

  useEffect(() => {
    if (!status) return;
    if (status !== 'generating' && !waitingQuestion && !waitingReply) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const { current, list } = await load();
        if (!alive) return;
        if (replyId) {
          const settled = list.find((message) => message.id === replyId);
          if (settled && settled.status !== 'pending') {
            setReplyId(null);
            const currentStep = current.steps[current.current_step];
            if (!currentStep?.understood_value) {
              setUnclear(true);
              say('app.writing.not_understood');
            }
            return;
          }
        }
      } catch {
        if (!alive) return;
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };
    timer = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [status, waitingQuestion, waitingReply, replyId, load, say]);

  useEffect(() => {
    if (question && question.status === 'ready' && playedQuestion.current !== question.id) {
      playedQuestion.current = question.id;
      playClip.current(question.id, question.audio_url);
    }
  }, [question]);

  const send = async (value: Answer & { textLanguage?: TextLanguage }) => {
    if (!writing) return;
    setBusy(true);
    setUnclear(false);
    setAnswer({ audio: value.audio, text: value.text });
    try {
      const pending = await api.answerWriting(writing.id, value);
      setReplyId(pending.id);
      setMessages((current) => [...current, pending]);
    } catch (error) {
      setAnswer(null);
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = async () => {
    if (recorder.recording) {
      const audio = await recorder.stop();
      if (audio) await send({ audio });
      return;
    }
    clips.stop();
    if (!(await recorder.start())) sayText('Autorise le micro, ou réponds au clavier.');
  };

  const confirm = async (accepted: boolean) => {
    if (!writing) return;
    setBusy(true);
    try {
      const updated = await api.confirmWriting(writing.id, accepted);
      setWriting(updated);
      setAnswer(null);
      setUnclear(false);
      setMessages(await api.messages(updated.conversation_id));
      if (updated.status !== 'collecting') refreshMe();
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    if (!writing) return;
    setBusy(true);
    try {
      const updated = await api.skipWriting(writing.id);
      setWriting(updated);
      setAnswer(null);
      setUnclear(false);
      setMessages(await api.messages(updated.conversation_id));
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const restart = async () => {
    if (!writing) return;
    setBusy(true);
    try {
      const fresh = await api.startWriting(writing.type);
      router.replace(`/ecrit/${fresh.id}`);
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  if (!writing) return <Loading />;

  const isCv = writing.type === 'cv_cover_letter';
  const understood = step?.understood_value && !step.confirmed ? step.understood_value : null;
  const noted = writing.steps.filter((item) => item.confirmed && item.understood_value);
  const position = Math.min(writing.current_step + 1, writing.total_steps);
  const collecting = writing.status === 'collecting';

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={{ flex: 1, backgroundColor: colors.sand }}
    >
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top, paddingHorizontal: 20, paddingBottom: 16, gap: 14 }}
        keyboardShouldPersistTaps="handled"
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <BackButton />
          <View style={{ flex: 1 }}>
            <T display w={700} size={22} lh={1.1}>
              {isCv ? 'Mon CV' : writing.title_fr}
            </T>
            <T size={13} color={colors.muted}>
              {isCv ? 'CV et lettre de motivation' : 'Écrit en français par Leeral'}
            </T>
          </View>
          <ScreenSpeaker prompt="app.writing.screen" />
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ flex: 1, flexDirection: 'row', gap: 4 }}>
            {Array.from({ length: writing.total_steps }, (_, index) => (
              <View
                key={index}
                style={{
                  flex: 1,
                  height: 6,
                  borderRadius: 3,
                  backgroundColor:
                    index < (collecting ? position : writing.total_steps) ? colors.light : colors.line,
                }}
              />
            ))}
          </View>
          <T display w={800} size={15} color={colors.lightInk}>
            {collecting ? `Question ${position} sur ${writing.total_steps}` : 'Terminé'}
          </T>
        </View>

        {collecting && step ? (
          <>
            <View style={{ gap: 10 }}>
              <View style={{ maxWidth: 300, gap: 4 }}>
                <T w={700} size={12} color={colors.label} style={{ paddingLeft: 4 }}>
                  Leeral te demande
                </T>
                <View
                  style={{
                    backgroundColor: colors.night,
                    borderRadius: 20,
                    borderBottomLeftRadius: 6,
                    paddingVertical: 12,
                    paddingHorizontal: 14,
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 12,
                  }}
                >
                  <Tap
                    accessibilityRole="button"
                    accessibilityLabel="Réécouter la question"
                    disabled={!question?.audio_url}
                    onPress={() => question && clips.play(question.id, question.audio_url)}
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 22,
                      backgroundColor: colors.light,
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {waitingQuestion ? (
                      <ActivityIndicator color={colors.night} />
                    ) : (
                      <Icon
                        name={question && clips.isPlaying(question.id) ? 'pause' : 'soundSmall'}
                        size={20}
                        color={colors.night}
                      />
                    )}
                  </Tap>
                  <T display w={700} size={18} lh={1.2} color={colors.sand} style={{ flex: 1 }}>
                    {step.question_fr}
                  </T>
                </View>
                {!step.required ? (
                  <Tap
                    accessibilityRole="button"
                    onPress={skip}
                    disabled={busy}
                    style={{ alignSelf: 'flex-start', height: 36, justifyContent: 'center', paddingLeft: 4 }}
                  >
                    <T w={700} size={13.5} color={colors.label} style={{ textDecorationLine: 'underline' }}>
                      Je n&apos;ai pas de réponse, passer
                    </T>
                  </Tap>
                ) : null}
              </View>

              {answer ? (
                <View style={{ alignSelf: 'flex-end', alignItems: 'flex-end', gap: 4, maxWidth: 290 }}>
                  <T w={700} size={12} color={colors.label} style={{ paddingRight: 4 }}>
                    Ta réponse
                  </T>
                  <View
                    style={{
                      backgroundColor: colors.lightSoft,
                      borderRadius: 20,
                      borderBottomRightRadius: 6,
                      paddingVertical: 10,
                      paddingHorizontal: 12,
                    }}
                  >
                    {answer.audio ? (
                      <VoiceNote
                        tone="mine"
                        label="Réécouter ma réponse"
                        bars={barsFor(answer.audio.uri, 16, 8, 24)}
                        playing={clips.isPlaying(answer.audio.uri)}
                        progress={clips.progressOf(answer.audio.uri)}
                        duration={null}
                        onPress={() => answer.audio && clips.play(answer.audio.uri, answer.audio.uri)}
                      />
                    ) : (
                      <T size={15}>{answer.text}</T>
                    )}
                  </View>
                </View>
              ) : null}
            </View>

            {waitingReply || busy ? (
              <View
                style={{
                  backgroundColor: colors.paper,
                  borderRadius: 22,
                  padding: 16,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <ActivityIndicator color={colors.night} />
                <T w={600} size={15}>
                  {waitingReply ? 'Je comprends ta réponse…' : 'Un instant…'}
                </T>
              </View>
            ) : understood ? (
              <View style={{ backgroundColor: colors.paper, borderRadius: 22, padding: 16, gap: 12 }}>
                <MiniSpeaker
                  prompt="app.writing.understood"
                  label="Écouter : ce que Leeral a compris"
                  width={44}
                  height={44}
                  style={{ position: 'absolute', top: 6, right: 6, zIndex: 2 }}
                />
                <T w={700} size={12} ls={1.4} upper color={colors.label}>
                  Leeral a compris
                </T>
                <T
                  display
                  w={800}
                  size={understood.length > 24 ? 24 : 40}
                  ls={-1}
                  lh={1.05}
                  style={{ paddingRight: 30 }}
                >
                  {understood}
                </T>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <Tap
                    accessibilityRole="button"
                    onPress={() => confirm(true)}
                    style={{
                      flex: 1,
                      height: 50,
                      borderRadius: 16,
                      backgroundColor: colors.river,
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                    }}
                  >
                    <Icon name="check" size={18} strokeWidth={2.6} color={colors.white} />
                    <T w={700} size={15} color={colors.white}>
                      C&apos;est juste
                    </T>
                  </Tap>
                  <Tap
                    accessibilityRole="button"
                    onPress={() => confirm(false)}
                    style={{
                      flex: 1,
                      height: 50,
                      borderRadius: 16,
                      backgroundColor: colors.sand,
                      borderWidth: 1,
                      borderColor: colors.line,
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                    }}
                  >
                    <Icon name="penBare" size={18} />
                    <T w={700} size={15}>
                      Corriger
                    </T>
                  </Tap>
                </View>
              </View>
            ) : unclear ? (
              <View style={{ backgroundColor: colors.claySoft, borderRadius: 22, padding: 16, gap: 6 }}>
                <T w={700} size={16} color={colors.clayInk}>
                  Je n&apos;ai pas bien compris.
                </T>
                <T size={14} color={colors.clayInk}>
                  Redis ta réponse avec le micro, ou écris-la au clavier.
                </T>
              </View>
            ) : null}

            {noted.length ? (
              <View style={{ gap: 6 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <T w={700} size={12} ls={1.4} upper color={colors.label} style={{ flex: 1 }}>
                    Déjà noté
                  </T>
                  <MiniSpeaker prompt="app.writing.noted" label="Écouter : déjà noté" />
                </View>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {noted.map((item) => (
                    <View
                      key={item.position}
                      style={{
                        minHeight: 32,
                        paddingHorizontal: 12,
                        paddingVertical: 6,
                        borderRadius: 16,
                        backgroundColor: colors.riverSoft,
                        justifyContent: 'center',
                        maxWidth: '100%',
                      }}
                    >
                      <T w={600} size={13.5} color={colors.riverInk} numberOfLines={1}>
                        {item.understood_value}
                      </T>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}
          </>
        ) : writing.status === 'generating' ? (
          <View
            style={{
              backgroundColor: colors.night,
              borderRadius: 24,
              padding: 20,
              gap: 12,
              alignItems: 'center',
            }}
          >
            <ActivityIndicator color={colors.light} size="large" />
            <T display w={700} size={20} color={colors.sand} center>
              J&apos;écris ton document en français…
            </T>
            <T size={14} color={colors.onNightMuted} center>
              Ça prend environ une minute.
            </T>
          </View>
        ) : writing.status === 'failed' ? (
          <View style={{ backgroundColor: colors.paper, borderRadius: 22, padding: 16, gap: 12 }}>
            <T w={700} size={16}>
              Je n&apos;ai pas pu terminer ce document.
            </T>
            <PrimaryButton label="Recommencer" height={52} size={17} loading={busy} onPress={restart} />
          </View>
        ) : null}
      </ScrollView>

      {collecting && step && !understood ? (
        <View
          style={{
            paddingTop: 8,
            paddingHorizontal: 20,
            paddingBottom: insets.bottom - 2,
            alignItems: 'center',
            gap: 2,
          }}
        >
          {typing ? (
            <TextAnswer
              language={language}
              placeholder="Écris ta réponse"
              busy={busy || waitingReply}
              onSend={(text, written) => send({ text, textLanguage: written })}
              onClose={() => setTyping(false)}
            />
          ) : (
            <>
              {recorder.recording ? <LiveBars /> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
                <Tap
                  accessibilityRole="button"
                  accessibilityLabel="Répondre au clavier"
                  onPress={() => setTyping(true)}
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 24,
                    backgroundColor: colors.paper,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon name="keyboard" size={20} />
                </Tap>
                <MicButton
                  recording={recorder.recording}
                  busy={busy || waitingReply || waitingQuestion}
                  onPress={toggleMic}
                  idleLabel="Appuyer pour répondre à voix haute"
                  recordingLabel="Envoyer ma réponse"
                />
                <MiniSpeaker
                  prompt="app.writing.micro"
                  label="Écouter : comment répondre"
                  width={48}
                  height={48}
                />
              </View>
              <T w={700} size={15}>
                {recorder.recording ? 'Je t’écoute… touche pour envoyer' : 'Réponds à voix haute'}
              </T>
            </>
          )}
        </View>
      ) : null}

      <SayBubble top={insets.top + 72} />
    </KeyboardAvoidingView>
  );
}
