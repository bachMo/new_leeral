import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, View } from 'react-native';

import { BottomNav } from '@/components/BottomNav';
import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import { MiniSpeaker, SayBubble, ScreenSpeaker, Tap, useInsets, useScreenVoice } from '@/components/ui';
import { api } from '@/lib/api';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { Writing, WritingType } from '@/lib/types';

const TYPES: { type: WritingType; label: string; sub: string; tint: string; ink: string; icon: string }[] = [
  {
    type: 'cv_cover_letter',
    label: 'CV et lettre',
    sub: 'Pour un emploi',
    tint: colors.lightSoft,
    ink: colors.lightInk,
    icon: 'M4 8h16v11H4zM9 8V5.5h6V8M4 13h16',
  },
  {
    type: 'request_letter',
    label: 'Demande',
    sub: 'Mairie, école, administration',
    tint: colors.adminSoft,
    ink: colors.night,
    icon: 'M4 21h16M5 21V10l7-5 7 5v11M9 21v-6h6v6',
  },
  {
    type: 'bank_letter',
    label: 'Banque',
    sub: 'Délai, réclamation',
    tint: colors.riverSoft,
    ink: colors.riverInk,
    icon: 'M3 7h18v11H3zM3 11h18M7 15h3',
  },
  {
    type: 'other',
    label: 'Autre courrier',
    sub: 'Tu me dis, j’écris',
    tint: colors.claySoft,
    ink: colors.clayInk,
    icon: 'M4 6h16v12H4zM4 7l8 6 8-6',
  },
];

export default function WriteChooseScreen() {
  const insets = useInsets();
  const { me, isGuest, refreshMe } = useSession();
  const { sayError } = useScreenVoice();
  const [resume, setResume] = useState<Writing | null>(null);
  const [starting, setStarting] = useState<WritingType | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      if (!isGuest) {
        refreshMe();
        api
          .writings()
          .then((list) => alive && setResume(list.find((item) => item.status === 'collecting') ?? null))
          .catch(() => undefined);
      }
      return () => {
        alive = false;
      };
    }, [isGuest, refreshMe]),
  );

  const start = async (type: WritingType) => {
    if (isGuest) {
      router.push({ pathname: '/numero', params: { next: '/ecrire' } });
      return;
    }
    setStarting(type);
    try {
      const writing = await api.startWriting(type);
      router.push(`/ecrit/${writing.id}`);
    } catch (error) {
      await sayError(error);
    } finally {
      setStarting(null);
    }
  };

  const usage = me?.usage;
  const plus = me?.plan.code === 'leeral_plus';
  const remaining = usage ? Math.max(usage.writings_limit - usage.writings_used, 0) : 0;
  const footer = isGuest
    ? 'Avec ton numéro, 1 document gratuit par mois'
    : plus
      ? `${remaining} document${remaining > 1 ? 's' : ''} restant${remaining > 1 ? 's' : ''} ce mois`
      : `${remaining} document${remaining > 1 ? 's' : ''} gratuit${remaining > 1 ? 's' : ''} ce mois`;

  return (
    <View style={{ flex: 1, backgroundColor: colors.sand }}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top, paddingHorizontal: 20, paddingBottom: 24, gap: 16 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <T display w={700} size={30} lh={1.05} ls={-0.8}>
              Écrire pour moi
            </T>
            <T size={15} lh={1.4} color={colors.muted} style={{ marginTop: 6 }}>
              Tu parles dans ta langue, j&apos;écris en français.
            </T>
          </View>
          <ScreenSpeaker prompt="app.write.screen" />
        </View>

        {resume ? (
          <View
            style={{
              backgroundColor: colors.night,
              borderRadius: 24,
              paddingVertical: 14,
              paddingLeft: 14,
              paddingRight: 6,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <View
              style={{
                width: 48,
                height: 58,
                borderRadius: 10,
                backgroundColor: colors.sand,
                paddingVertical: 9,
                paddingHorizontal: 8,
                gap: 4,
              }}
            >
              <View
                style={{
                  height: 3,
                  width: '70%',
                  backgroundColor: colors.night,
                  opacity: 0.5,
                  borderRadius: 2,
                }}
              />
              <View style={{ height: 3, backgroundColor: colors.night, opacity: 0.2, borderRadius: 2 }} />
              <View style={{ height: 3, backgroundColor: colors.light, borderRadius: 2 }} />
              <View
                style={{
                  height: 3,
                  width: '60%',
                  backgroundColor: colors.night,
                  opacity: 0.2,
                  borderRadius: 2,
                }}
              />
            </View>
            <Tap
              accessibilityRole="button"
              onPress={() => router.push(`/ecrit/${resume.id}`)}
              style={{ flex: 1, minWidth: 0, gap: 2 }}
            >
              <T w={700} size={12} ls={1.2} upper color={colors.light}>
                À terminer
              </T>
              <T w={700} size={16} lh={1.25} color={colors.sand}>
                {resume.title_fr}
              </T>
              <T size={13} color={colors.onNightMuted}>
                Question {Math.min(resume.current_step + 1, resume.total_steps)} sur {resume.total_steps}
              </T>
            </Tap>
            <MiniSpeaker
              prompt="app.write.resume"
              label="Écouter : document à terminer"
              color={colors.sand}
              width={40}
              height={44}
              opacity={0.6}
            />
          </View>
        ) : null}

        <T w={700} size={12} ls={1.4} upper color={colors.label} style={{ marginBottom: -6 }}>
          {resume ? 'Ou choisis ce que tu veux écrire' : 'Choisis ce que tu veux écrire'}
        </T>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {TYPES.map((item) => (
            <View
              key={item.type}
              style={{ width: '48.5%', flexGrow: 1, backgroundColor: colors.paper, borderRadius: 22 }}
            >
              <Tap
                accessibilityRole="button"
                accessibilityLabel={item.label}
                disabled={starting !== null}
                onPress={() => start(item.type)}
                style={{ minHeight: 128, padding: 14, justifyContent: 'space-between', gap: 12 }}
              >
                <View
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 15,
                    backgroundColor: item.tint,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {starting === item.type ? (
                    <ActivityIndicator color={item.ink} />
                  ) : (
                    <Icon path={item.icon} size={24} color={item.ink} />
                  )}
                </View>
                <View style={{ gap: 2 }}>
                  <T display w={700} size={17} lh={1.15}>
                    {item.label}
                  </T>
                  <T size={12.5} color={colors.muted}>
                    {item.sub}
                  </T>
                </View>
              </Tap>
              <MiniSpeaker
                prompt={`app.write.${item.type}`}
                label={`Écouter : ${item.label}`}
                width={40}
                height={40}
                opacity={0.5}
                style={{ position: 'absolute', top: 8, right: 6 }}
              />
            </View>
          ))}
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Icon name="info" size={16} color={colors.muted} />
          <T size={13.5} color={colors.muted} style={{ flex: 1 }}>
            {footer}
            {plus ? null : (
              <>
                {' · '}
                <T
                  w={700}
                  size={13.5}
                  style={{ textDecorationLine: 'underline' }}
                  onPress={() => router.push('/plus')}
                >
                  Leeral+
                </T>
              </>
            )}
          </T>
        </View>
      </ScrollView>
      <BottomNav active="write" />
      <SayBubble bottom={90 + Math.max(insets.bottom - 24, 0)} />
    </View>
  );
}
