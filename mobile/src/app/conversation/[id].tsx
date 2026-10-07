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
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { barsFor, VoiceNote } from '@/components/VoiceNote';
import { api } from '@/lib/api';
import { audioBus, formatDuration } from '@/lib/audio';
import { useClipPlayer } from '@/lib/clips';
import { useVoiceRecorder } from '@/lib/recorder';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { DocumentDetail, Message, TextLanguage } from '@/lib/types';

export default function ConversationScreen() {
  const { id, doc: documentId } = useLocalSearchParams<{ id: string; doc?: string }>();
  const insets = useInsets();
  const { language } = useSession();
  const { sayText, sayError, rate } = useScreenVoice();
  const clips = useClipPlayer(rate);
  const recorder = useVoiceRecorder();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const played = useRef(new Set<string>());
  const scroll = useRef<ScrollView>(null);
  const firstLoad = useRef(true);
  const playClip = useRef(clips.play);
  playClip.current = clips.play;

  const load = useCallback(async () => {
    const list = await api.messages(id);
    if (firstLoad.current) {
      list
        .filter((message) => message.status !== 'pending')
        .forEach((message) => played.current.add(message.id));
      firstLoad.current = false;
    }
    setMessages(list);
    return list;
  }, [id]);

  useEffect(() => {
    load().catch(sayError);
    if (documentId)
      api
        .document(documentId)
        .then(setDoc)
        .catch(() => undefined);
  }, [documentId, load, sayError]);

  const pending = messages.some((message) => message.status === 'pending');

  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => load().catch(() => undefined), 1500);
    return () => clearInterval(timer);
  }, [pending, load]);

  useEffect(() => {
    const fresh = messages.find(
      (message) =>
        message.role === 'assistant' && message.status === 'ready' && !played.current.has(message.id),
    );
    if (fresh && !audioBus.recording) {
      played.current.add(fresh.id);
      playClip.current(fresh.id, fresh.audio_url);
    }
    const failed = messages.find((message) => message.status === 'failed' && !played.current.has(message.id));
    if (failed) {
      played.current.add(failed.id);
      sayText("Je n'ai pas pu répondre. Repose ta question, s'il te plaît.");
    }
    setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 80);
  }, [messages, sayText]);

  const submit = async (question: Parameters<typeof api.ask>[1]) => {
    setSending(true);
    try {
      const exchange = await api.ask(id, question);
      played.current.add(exchange.question.id);
      setMessages((current) => [...current, exchange.question, exchange.answer]);
    } catch (error) {
      await sayError(error);
    } finally {
      setSending(false);
    }
  };

  const toggleMic = async () => {
    if (recorder.recording) {
      const audio = await recorder.stop();
      if (audio) await submit({ audio });
      return;
    }
    clips.stop();
    if (!(await recorder.start())) sayText('Autorise le micro pour poser ta question à voix haute.');
  };

  const sendText = (text: string, written: TextLanguage) => submit({ text, textLanguage: written });

  const asked = new Set(messages.map((message) => message.suggested_question_id).filter(Boolean));
  const suggestions = (doc?.suggested_questions ?? []).filter((item) => !asked.has(item.id)).slice(0, 3);
  const explanationDuration = doc?.explanation?.audio_duration_s;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={{ flex: 1, backgroundColor: colors.sand }}
    >
      <StatusBar style="dark" />
      <View
        style={{
          paddingTop: insets.top,
          paddingHorizontal: 20,
          paddingBottom: 12,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 10,
          borderBottomWidth: 1,
          borderBottomColor: colors.line,
        }}
      >
        <BackButton label="Retour à l'explication" />
        <View style={{ flex: 1, minWidth: 0 }}>
          <T display w={700} size={20} lh={1.1} numberOfLines={1}>
            {doc?.title ?? 'Mes questions'}
          </T>
          <T size={13} color={colors.muted}>
            Tes questions sur ce document
          </T>
        </View>
        {documentId ? (
          <Tap
            accessibilityRole="button"
            accessibilityLabel="Réécouter l'explication"
            onPress={() => router.back()}
            style={{
              height: 44,
              paddingHorizontal: 12,
              borderRadius: 22,
              backgroundColor: colors.night,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Icon name="play" size={12} color={colors.light} />
            <T w={700} size={13} color={colors.light}>
              {explanationDuration ? formatDuration(explanationDuration) : 'Écouter'}
            </T>
          </Tap>
        ) : null}
        <ScreenSpeaker prompt="app.conversation.screen" />
      </View>

      <ScrollView
        ref={scroll}
        style={{ flex: 1 }}
        contentContainerStyle={{
          flexGrow: 1,
          justifyContent: 'flex-end',
          paddingHorizontal: 20,
          paddingVertical: 14,
          gap: 12,
        }}
        keyboardShouldPersistTaps="handled"
      >
        {messages.map((message) =>
          message.role === 'user' ? (
            <View
              key={message.id}
              style={{ alignSelf: 'flex-end', maxWidth: 290, alignItems: 'flex-end', gap: 4 }}
            >
              <T w={700} size={12} color={colors.label}>
                Toi
              </T>
              {message.audio_url ? (
                <View
                  style={{
                    backgroundColor: colors.lightSoft,
                    borderRadius: 20,
                    borderBottomRightRadius: 6,
                    paddingVertical: 10,
                    paddingHorizontal: 12,
                  }}
                >
                  <VoiceNote
                    tone="mine"
                    label="Réécouter ma question"
                    bars={barsFor(message.id, 16, 8, 20)}
                    playing={clips.isPlaying(message.id)}
                    progress={clips.progressOf(message.id)}
                    duration={message.audio_duration_s}
                    onPress={() => clips.play(message.id, message.audio_url)}
                  />
                </View>
              ) : null}
              {message.text ? (
                <T
                  size={message.audio_url ? 13.5 : 15}
                  color={message.audio_url ? colors.muted : colors.night}
                  style={
                    message.audio_url
                      ? { fontStyle: 'italic', paddingRight: 4 }
                      : {
                          backgroundColor: colors.lightSoft,
                          borderRadius: 18,
                          paddingVertical: 10,
                          paddingHorizontal: 12,
                          overflow: 'hidden',
                        }
                  }
                >
                  {message.audio_url ? `« ${message.text} »` : message.text}
                </T>
              ) : message.status === 'pending' ? (
                <T size={13.5} color={colors.muted} style={{ fontStyle: 'italic' }}>
                  J&apos;écoute ta question…
                </T>
              ) : null}
            </View>
          ) : (
            <View key={message.id} style={{ maxWidth: 330, gap: 4 }}>
              <T w={700} size={12} color={colors.label} style={{ paddingLeft: 4 }}>
                Leeral
              </T>
              <View
                style={{
                  backgroundColor: colors.night,
                  borderRadius: 20,
                  borderBottomLeftRadius: 6,
                  paddingVertical: 12,
                  paddingHorizontal: 14,
                  gap: 10,
                }}
              >
                {message.status === 'pending' ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <ActivityIndicator color={colors.light} />
                    <T size={15} color={colors.sand}>
                      Je cherche la réponse dans ton document…
                    </T>
                  </View>
                ) : message.status === 'failed' ? (
                  <T size={15} color={colors.sand}>
                    Je n&apos;ai pas pu répondre. Repose ta question.
                  </T>
                ) : (
                  <>
                    {message.audio_url ? (
                      <VoiceNote
                        tone="leeral"
                        label="Écouter la réponse"
                        bars={barsFor(message.id, 18, 8, 24)}
                        playing={clips.isPlaying(message.id)}
                        progress={clips.progressOf(message.id)}
                        duration={message.audio_duration_s}
                        onPress={() => clips.play(message.id, message.audio_url)}
                      />
                    ) : null}
                    <T size={15} lh={1.4} color={colors.sand}>
                      {message.text_fr ?? message.text}
                    </T>
                    {message.source_quote ? (
                      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6 }}>
                        <Icon name="fileLines" size={14} color={colors.light} />
                        <T w={600} size={12.5} color={colors.light} style={{ flex: 1 }}>
                          Écrit sur le document : « {message.source_quote} »
                        </T>
                      </View>
                    ) : null}
                  </>
                )}
              </View>
            </View>
          ),
        )}

        {suggestions.length ? (
          <View style={{ gap: 6 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <T w={700} size={12} ls={1.4} upper color={colors.label} style={{ flex: 1 }}>
                Questions fréquentes
              </T>
              <MiniSpeaker prompt="app.conversation.suggestions" label="Écouter : questions fréquentes" />
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {suggestions.map((item) => (
                <Tap
                  key={item.id}
                  accessibilityRole="button"
                  disabled={sending}
                  onPress={() => submit({ suggestedId: item.id })}
                  onLongPress={() => clips.play(item.id, item.audio_url)}
                  style={{
                    minHeight: 44,
                    paddingHorizontal: 14,
                    paddingVertical: 8,
                    borderRadius: 22,
                    backgroundColor: colors.paper,
                    borderWidth: 1,
                    borderColor: colors.line,
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 6,
                    maxWidth: '100%',
                  }}
                >
                  <Icon name="soundBare" size={14} />
                  <T w={600} size={14} style={{ flexShrink: 1 }}>
                    {item.text_fr}
                  </T>
                </Tap>
              ))}
            </View>
          </View>
        ) : null}
      </ScrollView>

      <View
        style={{
          paddingTop: 12,
          paddingHorizontal: 20,
          paddingBottom: insets.bottom,
          backgroundColor: colors.paper,
          borderTopWidth: 1,
          borderTopColor: colors.line,
          alignItems: 'center',
          gap: 8,
        }}
      >
        {typing ? (
          <TextAnswer
            language={language}
            placeholder="Écris ta question"
            busy={sending}
            onSend={sendText}
            onClose={() => setTyping(false)}
          />
        ) : (
          <>
            {recorder.recording ? <LiveBars /> : null}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 18 }}>
              <Tap
                accessibilityRole="button"
                accessibilityLabel="Écrire ma question au clavier"
                onPress={() => setTyping(true)}
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 24,
                  backgroundColor: colors.sand,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon name="keyboard" size={20} />
              </Tap>
              <MicButton
                recording={recorder.recording}
                busy={sending}
                onPress={toggleMic}
                idleLabel="Appuyer pour poser une question"
                recordingLabel="Envoyer ma question"
              />
              <MiniSpeaker
                prompt="app.conversation.micro"
                label="Écouter : comment poser une question"
                width={48}
                height={48}
              />
            </View>
            <T w={700} size={15}>
              {sending
                ? 'J’envoie ta question…'
                : recorder.recording
                  ? 'Je t’écoute… touche pour envoyer'
                  : 'Touche et pose ta question'}
            </T>
          </>
        )}
      </View>

      <SayBubble top={insets.top + 72} />
    </KeyboardAvoidingView>
  );
}
