import * as Speech from 'expo-speech';
import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  Halo,
  MiniSpeaker,
  PrimaryButton,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api, asApiError, type ApiError } from '@/lib/api';
import { audioBus, enablePlayback } from '@/lib/audio';
import { useClipPlayer } from '@/lib/clips';
import { plural } from '@/lib/format';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { PracticeAnswer, PracticeRound, Word } from '@/lib/types';

type Tab = 'core' | 'mine';

async function speakFrench(word: string, rate: number) {
  if (audioBus.recording) return;
  audioBus.claim('speech', () => Speech.stop());
  await Speech.stop();
  await enablePlayback();
  Speech.speak(word, { language: 'fr-FR', rate: rate < 1 ? 0.75 : 0.9 });
}

export default function LearnScreen() {
  const insets = useInsets();
  const { me } = useSession();
  const { say, sayError, rate } = useScreenVoice();
  const clips = useClipPlayer(rate);
  const [tab, setTab] = useState<Tab>('core');
  const [mastered, setMastered] = useState<number | null>(null);
  const [round, setRound] = useState<PracticeRound | null>(null);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<PracticeAnswer | null>(null);
  const [blocked, setBlocked] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [words, setWords] = useState<Word[] | null>(null);
  const [score, setScore] = useState<{ correct: number; total: number } | null>(null);

  const refreshOverview = useCallback(() => {
    api
      .learningOverview()
      .then((overview) => setMastered(overview.mastered_words))
      .catch(() => undefined);
  }, []);

  const startRound = useCallback(async () => {
    setLoading(true);
    setBlocked(null);
    try {
      const next = await api.startPractice();
      setRound(next);
      setIndex(0);
      setPicked(null);
      setResult(null);
      setScore(null);
    } catch (error) {
      setBlocked(asApiError(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      refreshOverview();
      return () => Speech.stop();
    }, [refreshOverview]),
  );

  useEffect(() => {
    startRound();
  }, [startRound]);

  useEffect(() => {
    if (tab !== 'mine' || words || !me?.plan.document_words) return;
    api.words().then(setWords).catch(sayError);
  }, [tab, words, me?.plan.document_words, sayError]);

  const exercise = round?.exercises[index];
  const finished = !!round && index >= round.exercises.length;

  useEffect(() => {
    if (exercise && tab === 'core') speakFrench(exercise.word_fr, rate);
  }, [exercise, tab, rate]);

  const choose = async (wordId: string) => {
    if (!round || !exercise || picked) return;
    setPicked(wordId);
    try {
      const answer = await api.answerPractice(round.session_id, exercise.word_id, wordId);
      setResult(answer);
      setScore({ correct: answer.correct_count, total: answer.total_count });
      say(answer.is_correct ? 'app.learn.right' : 'app.learn.wrong');
      refreshOverview();
    } catch (error) {
      setPicked(null);
      await sayError(error);
    }
  };

  const next = async () => {
    if (!round || !picked) return;
    const following = index + 1;
    setIndex(following);
    setPicked(null);
    setResult(null);
    if (following >= round.exercises.length) {
      await api.finishPractice(round.session_id).catch(() => undefined);
      say('app.learn.done');
    }
  };

  const correctId = result?.correct_word_id ?? null;

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
            <T display w={700} size={22} lh={1.1}>
              Apprendre le français
            </T>
            <T w={700} size={13} color={colors.river}>
              {mastered === null ? ' ' : `${plural(mastered, 'mot')} appris`}
            </T>
          </View>
          <ScreenSpeaker prompt="app.learn.screen" />
        </View>

        <View>
          <View
            style={{
              flexDirection: 'row',
              gap: 4,
              backgroundColor: colors.sandDark,
              borderRadius: 16,
              padding: 4,
              paddingRight: 44,
            }}
          >
            {(['core', 'mine'] as Tab[]).map((item) => (
              <Tap
                key={item}
                accessibilityRole="button"
                accessibilityState={{ selected: tab === item }}
                onPress={() => setTab(item)}
                style={{
                  flex: 1,
                  height: 40,
                  borderRadius: 12,
                  backgroundColor: tab === item ? colors.paper : 'transparent',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <T w={tab === item ? 700 : 600} size={14} color={tab === item ? colors.night : colors.muted}>
                  {item === 'core' ? 'Mots essentiels' : 'Mes documents'}
                </T>
              </Tap>
            ))}
          </View>
          <MiniSpeaker
            prompt="app.learn.tabs"
            label="Écouter : les onglets"
            style={{ position: 'absolute', right: 4, top: 4 }}
          />
        </View>

        {tab === 'mine' ? (
          !me?.plan.document_words ? (
            <View style={{ backgroundColor: colors.paper, borderRadius: 28, padding: 20, gap: 12 }}>
              <T display w={700} size={20}>
                Les mots de tes documents
              </T>
              <T size={15} lh={1.45} color={colors.muted}>
                Avec Leeral+, j&apos;apprends avec toi les mots français trouvés dans tes propres documents.
              </T>
              <PrimaryButton
                label="Découvrir Leeral+"
                height={54}
                size={17}
                onPress={() => router.push('/plus')}
              />
            </View>
          ) : !words ? (
            <ActivityIndicator color={colors.night} style={{ marginTop: 30 }} />
          ) : words.length === 0 ? (
            <View style={{ backgroundColor: colors.paper, borderRadius: 22, padding: 16 }}>
              <T size={15} color={colors.muted}>
                Pas encore de mots. Fais expliquer un document et ses mots apparaîtront ici.
              </T>
            </View>
          ) : (
            words.map((word) => (
              <View
                key={word.word_id}
                style={{
                  backgroundColor: colors.paper,
                  borderRadius: 18,
                  padding: 10,
                  paddingLeft: 12,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <Tap
                  accessibilityRole="button"
                  accessibilityLabel={`Écouter ${word.word_fr}`}
                  onPress={() => speakFrench(word.word_fr, rate)}
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 22,
                    backgroundColor: colors.riverSoft,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon name="soundSmall" size={18} color={colors.river} />
                </Tap>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <T display w={700} size={18}>
                    {word.word_fr}
                  </T>
                  {word.meaning ? (
                    <T size={13.5} color={colors.muted} numberOfLines={2}>
                      {word.meaning}
                    </T>
                  ) : null}
                </View>
                {word.meaning_audio_url ? (
                  <MiniSpeaker
                    label="Écouter dans ma langue"
                    onPress={() => clips.play(word.word_id, word.meaning_audio_url)}
                  />
                ) : null}
                {word.mastered ? <Icon name="check" size={18} color={colors.river} /> : null}
              </View>
            ))
          )
        ) : loading ? (
          <ActivityIndicator color={colors.night} style={{ marginTop: 40 }} />
        ) : blocked ? (
          <View style={{ backgroundColor: colors.paper, borderRadius: 28, padding: 20, gap: 12 }}>
            <T display w={700} size={20}>
              {blocked.code === 'QUOTA_EXCEEDED'
                ? 'C’est tout pour aujourd’hui'
                : 'Pas d’exercice pour l’instant'}
            </T>
            <T size={15} lh={1.45} color={colors.muted}>
              {blocked.code === 'QUOTA_EXCEEDED'
                ? 'Ta formule gratuite donne une séance par jour. Avec Leeral+, tu révises sans limite.'
                : blocked.message}
            </T>
            {blocked.code === 'QUOTA_EXCEEDED' ? (
              <PrimaryButton
                label="Découvrir Leeral+"
                height={54}
                size={17}
                onPress={() => router.push('/plus')}
              />
            ) : (
              <PrimaryButton label="Réessayer" height={54} size={17} onPress={startRound} />
            )}
          </View>
        ) : finished ? (
          <View
            style={{
              backgroundColor: colors.paper,
              borderRadius: 28,
              padding: 20,
              gap: 12,
              alignItems: 'center',
            }}
          >
            <Halo size={100} inset={12} core={60} color={colors.river} outer={0.12} middle={0.2}>
              <Icon name="check" size={28} color={colors.white} />
            </Halo>
            <T display w={800} size={26} center>
              Séance terminée
            </T>
            <T size={15} color={colors.muted} center>
              {score
                ? `${score.correct} bonne${score.correct > 1 ? 's' : ''} réponse${score.correct > 1 ? 's' : ''} sur ${score.total}`
                : 'Reviens demain pour réviser.'}
            </T>
            <PrimaryButton
              label="Encore une séance"
              height={54}
              size={17}
              style={{ alignSelf: 'stretch' }}
              onPress={startRound}
            />
          </View>
        ) : exercise ? (
          <>
            <View
              style={{
                backgroundColor: colors.paper,
                borderRadius: 28,
                paddingVertical: 18,
                paddingHorizontal: 20,
                alignItems: 'center',
                gap: 10,
              }}
            >
              <T w={700} size={12} ls={1.4} upper color={colors.riverInk}>
                Écoute et choisis
              </T>
              <Tap
                accessibilityRole="button"
                accessibilityLabel="Écouter le mot en français"
                onPress={() => speakFrench(exercise.word_fr, rate)}
              >
                <Halo size={100} inset={12} core={60} color={colors.river} outer={0.12} middle={0.2}>
                  <Icon name="sound" size={26} color={colors.white} />
                </Halo>
              </Tap>
              <T display w={800} size={40} ls={-1.2} lh={1} center numberOfLines={2} adjustsFontSizeToFit>
                {exercise.word_fr}
              </T>
              <T size={14} color={colors.muted} center numberOfLines={2}>
                {exercise.example_fr ?? `Mot ${index + 1} sur ${round?.exercises.length ?? 0}`}
              </T>
            </View>

            <View style={{ gap: 8 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <T w={700} size={12} ls={1.4} upper color={colors.label} style={{ flex: 1 }}>
                  Que veut dire ce mot ?
                </T>
                <MiniSpeaker prompt="app.learn.choices" label="Écouter : comment choisir" />
              </View>
              {exercise.choices.map((choice) => {
                const isPicked = picked === choice.word_id;
                const reveal = !!correctId && choice.word_id === correctId;
                const wrong = isPicked && !!result && !result.is_correct;
                const bg = reveal ? colors.river : wrong ? colors.claySoft : colors.paper;
                const fg = reveal ? colors.white : wrong ? colors.clayInk : colors.night;
                return (
                  <View
                    key={choice.word_id}
                    style={{
                      minHeight: 60,
                      borderRadius: 18,
                      backgroundColor: bg,
                      borderWidth: wrong ? 2 : reveal ? 0 : 1,
                      borderColor: wrong ? colors.clay : colors.line,
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                      paddingVertical: 8,
                      paddingLeft: 8,
                      paddingRight: 12,
                    }}
                  >
                    <Tap
                      accessibilityRole="button"
                      accessibilityLabel="Écouter cette réponse"
                      onPress={() => clips.play(choice.word_id, choice.meaning_audio_url)}
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 22,
                        backgroundColor: reveal
                          ? 'rgba(255,255,255,0.18)'
                          : wrong
                            ? colors.paper
                            : colors.sand,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon name="soundSmall" size={18} color={fg} />
                    </Tap>
                    <Tap
                      accessibilityRole="button"
                      accessibilityState={{ selected: isPicked }}
                      disabled={!!picked}
                      onPress={() => choose(choice.word_id)}
                      style={{ flex: 1, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 12 }}
                    >
                      <T w={700} size={16} lh={1.25} color={fg} style={{ flex: 1 }}>
                        {choice.meaning ?? choice.word_fr}
                      </T>
                      <T w={700} size={13} color={fg}>
                        {reveal ? 'Bravo !' : wrong ? 'Pas ça' : ''}
                      </T>
                    </Tap>
                  </View>
                );
              })}
            </View>
          </>
        ) : null}
      </ScrollView>

      {tab === 'core' && exercise && !finished && !blocked ? (
        <View style={{ paddingTop: 12, paddingHorizontal: 20, paddingBottom: insets.bottom }}>
          <PrimaryButton
            label="Mot suivant"
            height={60}
            size={18}
            bg={picked && result ? colors.night : colors.line}
            fg={picked && result ? colors.sand : colors.label}
            disabled={!picked || !result}
            onPress={next}
          />
        </View>
      ) : null}

      <SayBubble top={insets.top + 72} />
    </View>
  );
}
