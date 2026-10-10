import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { View } from 'react-native';

import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  Logo,
  PrimaryButton,
  SayBubble,
  Screen,
  ScreenSpeaker,
  Tap,
  useInsets,
  useLayout,
  useScreenVoice,
} from '@/components/ui';
import { LANGUAGE_NAMES } from '@/lib/format';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { Language } from '@/lib/types';

const LANGUAGES: { id: Language; hello: string; available: boolean }[] = [
  { id: 'wo', hello: 'Nanga def ?', available: true },
  { id: 'ff', hello: 'No mbaɗɗaa ?', available: true },
  { id: 'sr', hello: 'Na fiyo ?', available: false },
];

export default function LanguageScreen() {
  const { change } = useLocalSearchParams<{ change?: string }>();
  const insets = useInsets();
  const { fit } = useLayout();
  const { language, me, chooseLanguage } = useSession();
  const { say, sayError } = useScreenVoice();
  const [selected, setSelected] = useState<Language>(language === 'sr' ? 'wo' : language);
  const [busy, setBusy] = useState(false);

  const pick = (id: Language, available: boolean) => {
    if (!available) {
      say('app.language.soon', selected);
      return;
    }
    setSelected(id);
    say('app.language.picked', id);
  };

  const confirm = async () => {
    setBusy(true);
    try {
      if (!me || selected !== me.user.language) await chooseLanguage(selected);
      if (change && router.canGoBack()) router.back();
      else router.replace('/accueil');
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      background={colors.night}
      gap={fit(20)}
      footer={
        <PrimaryButton
          label="Continuer"
          height={fit(64)}
          size={20}
          bg={colors.light}
          fg={colors.night}
          loading={busy}
          onPress={confirm}
          right={<Icon name="arrow" size={22} color={colors.night} />}
        />
      }
      overlay={<SayBubble light bottom={insets.bottom + 80} />}
    >
      <StatusBar style="light" />
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end' }}>
        <ScreenSpeaker prompt="app.language.screen" dark />
      </View>

      <View style={{ alignItems: 'center', gap: fit(12) }}>
        <Logo size={fit(64)} inverted />
        <T display w={800} size={fit(34)} ls={-1} color={colors.sand} center>
          Choisis ta langue
        </T>
        <T size={16} lh={1.45} color={colors.onNightMuted} center style={{ maxWidth: 300 }}>
          Touche une langue pour l&apos;écouter. Leeral te parlera dans cette langue.
        </T>
      </View>

      <View style={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
        {LANGUAGES.map((item) => {
          const active = item.id === selected;
          return (
            <Tap
              key={item.id}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => pick(item.id, item.available)}
              style={{
                minHeight: fit(92),
                paddingVertical: 10,
                borderRadius: 26,
                backgroundColor: active ? colors.light : 'rgba(246,240,228,0.07)',
                borderWidth: active ? 0 : 1,
                borderColor: 'rgba(246,240,228,0.14)',
                flexDirection: 'row',
                alignItems: 'center',
                gap: 14,
                paddingLeft: 14,
                paddingRight: 16,
              }}
            >
              <View
                style={{
                  width: fit(60),
                  height: fit(60),
                  borderRadius: fit(30),
                  backgroundColor: active ? colors.night : 'rgba(244,166,42,0.18)',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon name="sound" size={fit(26)} color={colors.light} />
              </View>
              <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                <T
                  display
                  w={800}
                  size={fit(26)}
                  ls={-0.5}
                  numberOfLines={1}
                  adjustsFontSizeToFit
                  color={active ? colors.night : colors.sand}
                >
                  {LANGUAGE_NAMES[item.id]}
                </T>
                <T size={15} color={active ? colors.night : colors.sand} style={{ opacity: 0.8 }}>
                  « {item.hello} »{item.available ? '' : ' · bientôt'}
                </T>
              </View>
              {active ? (
                <View
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 16,
                    backgroundColor: colors.night,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon name="check" size={18} strokeWidth={3} color={colors.light} />
                </View>
              ) : null}
            </Tap>
          );
        })}
      </View>
    </Screen>
  );
}
