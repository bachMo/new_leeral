import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { ScrollView, View } from 'react-native';

import { BottomNav } from '@/components/BottomNav';
import { Icon, type IconName } from '@/components/Icon';
import { T } from '@/components/T';
import {
  Halo,
  Logo,
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useLayout,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { capture } from '@/lib/capture';
import { documentMeta, LANGUAGE_NAMES, plural } from '@/lib/format';
import { pickDocument, pickPhotos } from '@/lib/pickers';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { DocumentSummary, LocalFile } from '@/lib/types';

function QuickAction({
  icon,
  label,
  prompt,
  onPress,
}: {
  icon: IconName;
  label: string;
  prompt: string;
  onPress: () => void;
}) {
  return (
    <View style={{ flexGrow: 1, flexBasis: 150 }}>
      <Tap
        accessibilityRole="button"
        accessibilityLabel={label}
        onPress={onPress}
        style={{
          height: 48,
          borderRadius: 16,
          backgroundColor: 'rgba(246,240,228,0.08)',
          flexDirection: 'row',
          alignItems: 'center',
          paddingLeft: 14,
          paddingRight: 42,
          gap: 8,
        }}
      >
        <Icon name={icon} size={18} color={colors.sand} />
        <T w={600} size={15} color={colors.sand} numberOfLines={1} style={{ flexShrink: 1 }}>
          {label}
        </T>
      </Tap>
      <MiniSpeaker
        prompt={prompt}
        label={`Écouter : ${label}`}
        color={colors.sand}
        style={{ position: 'absolute', right: 6, top: 4 }}
      />
    </View>
  );
}

function FeatureCard({
  title,
  sub,
  bg,
  iconBg,
  icon,
  iconColor,
  subColor,
  prompt,
  onPress,
}: {
  title: string;
  sub: string;
  bg: string;
  iconBg: string;
  icon: IconName;
  iconColor: string;
  subColor: string;
  prompt: string;
  onPress: () => void;
}) {
  return (
    <View style={{ flexGrow: 1, flexBasis: 160 }}>
      <Tap
        accessibilityRole="button"
        accessibilityLabel={title}
        onPress={onPress}
        style={{
          backgroundColor: bg,
          borderRadius: 20,
          paddingVertical: 14,
          paddingLeft: 12,
          paddingRight: 34,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 8,
          minHeight: 76,
        }}
      >
        <View
          style={{
            width: 40,
            height: 40,
            borderRadius: 13,
            backgroundColor: iconBg,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name={icon} size={21} color={iconColor} />
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <T display w={700} size={14} lh={1.12}>
            {title}
          </T>
          <T size={12} color={subColor} style={{ marginTop: 2 }}>
            {sub}
          </T>
        </View>
      </Tap>
      <MiniSpeaker
        prompt={prompt}
        label={`Écouter : ${title}`}
        width={30}
        style={{ position: 'absolute', right: 2, top: '50%', marginTop: -20 }}
      />
    </View>
  );
}

export default function HomeScreen() {
  const insets = useInsets();
  const { fit, width } = useLayout();
  const { me, language, isGuest } = useSession();
  const { sayError } = useScreenVoice();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [learned, setLearned] = useState<number | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      if (!isGuest) {
        api
          .documents(2)
          .then((page) => alive && setDocs(page.items))
          .catch(() => undefined);
      }
      api
        .learningOverview()
        .then((overview) => alive && setLearned(overview.mastered_words))
        .catch(() => undefined);
      return () => {
        alive = false;
      };
    }, [isGuest]),
  );

  const start = (files: LocalFile[] | null) => {
    if (!files?.length) return;
    capture.set(files);
    router.push('/lecture');
  };

  const fromGallery = async () => {
    try {
      start(await pickPhotos());
    } catch (error) {
      await sayError(error);
    }
  };

  const fromFile = async () => {
    try {
      start(await pickDocument());
    } catch (error) {
      await sayError(error);
    }
  };

  const firstName = me?.user.first_name;
  const initial = (firstName ?? '?').charAt(0).toUpperCase();

  return (
    <View style={{ flex: 1, backgroundColor: colors.sand }}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top, paddingHorizontal: 20, paddingBottom: 24, gap: 16 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Logo size={36} />
          <View style={{ flex: 1, minWidth: 0 }}>
            {width >= 360 ? (
              <T display w={800} size={26} ls={-1} numberOfLines={1}>
                leeral
              </T>
            ) : null}
          </View>
          <View>
            <Tap
              accessibilityRole="button"
              accessibilityLabel="Changer de langue"
              onPress={() => router.push('/langue?change=1')}
              style={{
                height: 44,
                paddingLeft: 14,
                paddingRight: 38,
                borderRadius: 22,
                backgroundColor: colors.paper,
                borderWidth: 1,
                borderColor: colors.line,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 7,
              }}
            >
              <Icon name="globe" size={18} />
              <T w={700} size={15}>
                {LANGUAGE_NAMES[language]}
              </T>
            </Tap>
            <MiniSpeaker
              prompt="app.home.language"
              label="Écouter : changer de langue"
              style={{ position: 'absolute', right: 2, top: 2 }}
            />
          </View>
          {isGuest ? (
            <Tap
              accessibilityRole="button"
              accessibilityLabel="Me connecter"
              onPress={() => router.push('/numero')}
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
              <Icon name="user" size={20} />
            </Tap>
          ) : (
            <Tap
              accessibilityRole="button"
              accessibilityLabel="Mon compte"
              onPress={() => router.push('/profil')}
              style={{
                width: 44,
                height: 44,
                borderRadius: 22,
                backgroundColor: colors.night,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <T display w={800} size={17} color={colors.light}>
                {initial}
              </T>
            </Tap>
          )}
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <T display w={700} size={fit(30)} lh={1.05} ls={-0.8}>
              {isGuest || !firstName ? 'Bonjour !' : `Bonjour ${firstName}`}
            </T>
            <T size={15} color={colors.muted} style={{ marginTop: 6 }}>
              Que veux-tu comprendre aujourd&apos;hui ?
            </T>
          </View>
          <ScreenSpeaker prompt="app.home.screen" />
        </View>

        <View
          style={{
            backgroundColor: colors.night,
            borderRadius: 28,
            paddingTop: 18,
            paddingHorizontal: 18,
            paddingBottom: 16,
            alignItems: 'center',
            gap: 12,
          }}
        >
          <MiniSpeaker
            prompt="app.home.photo"
            label="Écouter : photographier un document"
            color={colors.sand}
            width={44}
            height={44}
            opacity={0.6}
            style={{ position: 'absolute', top: 10, right: 10, zIndex: 2 }}
          />
          <Tap
            accessibilityRole="button"
            accessibilityLabel="Prendre un document en photo"
            onPress={() => router.push('/camera')}
          >
            <Halo size={fit(120)} inset={fit(13)} core={fit(72)}>
              <Icon name="camera" size={fit(32)} color={colors.night} />
            </Halo>
          </Tap>
          <View style={{ alignItems: 'center' }}>
            <T display w={700} size={fit(22)} color={colors.sand} center>
              Photographier un document
            </T>
            <T size={14} color={colors.onNightMuted} center style={{ marginTop: 2 }}>
              Leeral te l&apos;explique à voix haute
            </T>
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignSelf: 'stretch' }}>
            <QuickAction icon="file" label="PDF / Word" prompt="app.home.file" onPress={fromFile} />
            <QuickAction icon="image" label="Galerie" prompt="app.home.gallery" onPress={fromGallery} />
          </View>
        </View>

        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          <FeatureCard
            title="Écrire pour moi"
            sub="CV, lettre, demande"
            bg={colors.lightSoft}
            iconBg={colors.light}
            icon="pen"
            iconColor={colors.night}
            subColor={colors.brown}
            prompt="app.home.write"
            onPress={() => router.navigate('/ecrire')}
          />
          <FeatureCard
            title="Apprendre le français"
            sub={learned === null ? 'Mots du quotidien' : `${plural(learned, 'mot')} appris`}
            bg={colors.riverSoft}
            iconBg={colors.river}
            icon="book"
            iconColor={colors.white}
            subColor={colors.riverInk}
            prompt="app.home.learn"
            onPress={() => router.push('/apprendre')}
          />
        </View>

        {isGuest ? (
          <View
            style={{
              backgroundColor: colors.paper,
              borderRadius: 22,
              padding: 16,
              gap: 12,
              borderWidth: 1.5,
              borderColor: colors.line,
            }}
          >
            <MiniSpeaker
              prompt="app.home.guest"
              label="Écouter : garder mes documents"
              width={44}
              height={44}
              style={{ position: 'absolute', top: 6, right: 6, zIndex: 2 }}
            />
            <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start', paddingRight: 40 }}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  backgroundColor: colors.sand,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon name="bookmark" size={20} />
              </View>
              <View style={{ flex: 1 }}>
                <T w={700} size={16}>
                  Tu utilises Leeral sans compte
                </T>
                <T size={13.5} lh={1.4} color={colors.muted} style={{ marginTop: 2 }}>
                  Tout marche, mais tes documents ne sont pas gardés.
                </T>
              </View>
            </View>
            <Tap
              accessibilityRole="button"
              onPress={() => router.push('/numero')}
              style={{
                height: 48,
                borderRadius: 16,
                backgroundColor: colors.night,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <T w={700} size={15} color={colors.sand}>
                Garder mes documents
              </T>
            </Tap>
          </View>
        ) : (
          <View style={{ gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <T display w={700} size={18} style={{ flex: 1 }}>
                Mes documents
              </T>
              <MiniSpeaker prompt="app.home.documents" label="Écouter : mes documents" />
              <Tap
                onPress={() => router.navigate('/documents')}
                style={{ height: 40, justifyContent: 'center' }}
              >
                <T w={700} size={14} style={{ textDecorationLine: 'underline' }}>
                  Tout voir
                </T>
              </Tap>
            </View>
            {docs.length === 0 ? (
              <View style={{ backgroundColor: colors.paper, borderRadius: 18, padding: 14 }}>
                <T size={14} color={colors.muted}>
                  Tes documents expliqués apparaîtront ici.
                </T>
              </View>
            ) : (
              docs.map((doc) => {
                const meta = documentMeta(doc);
                return (
                  <Tap
                    key={doc.id}
                    onPress={() =>
                      router.push(
                        doc.status === 'ready' ? `/explication/${doc.id}` : `/lecture?doc=${doc.id}`,
                      )
                    }
                    style={{
                      backgroundColor: colors.paper,
                      borderRadius: 18,
                      paddingVertical: 10,
                      paddingRight: 10,
                      paddingLeft: 14,
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <T w={700} size={16} numberOfLines={1}>
                        {doc.title ?? 'Document'}
                      </T>
                      <T w={600} size={13} color={meta.color} numberOfLines={1} style={{ marginTop: 2 }}>
                        {meta.text}
                      </T>
                    </View>
                    <View
                      accessibilityLabel="Réécouter l'explication"
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 22,
                        backgroundColor: colors.night,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon name="play" size={16} color={colors.light} />
                    </View>
                  </Tap>
                );
              })
            )}
          </View>
        )}
      </ScrollView>
      <BottomNav active="home" />
      <SayBubble bottom={90 + Math.max(insets.bottom - 24, 0)} />
    </View>
  );
}
