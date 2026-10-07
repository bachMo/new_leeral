import { router, useLocalSearchParams, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  MiniSpeaker,
  NumberPad,
  PrimaryButton,
  SayBubble,
  ScreenSpeaker,
  StepDots,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { formatDuration } from '@/lib/audio';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';

export default function CodeScreen() {
  const params = useLocalSearchParams<{
    phone: string;
    local: string;
    length?: string;
    resend?: string;
    next?: string;
  }>();
  const length = Math.min(Math.max(Number(params.length) || 4, 4), 8);
  const insets = useInsets();
  const { language, applyTokens } = useSession();
  const { sayError, sayText } = useScreenVoice();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(Number(params.resend) || 60);
  const submitted = useRef('');
  const full = code.length === length;
  const local = params.local ?? '';

  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  const verify = async (value: string) => {
    if (value.length !== length || busy || submitted.current === value) return;
    submitted.current = value;
    setBusy(true);
    try {
      const tokens = await api.verifyOtp(params.phone, value, language);
      const me = await applyTokens(tokens);
      const next = params.next || '/accueil';
      if (tokens.is_new_account || !me.user.first_name) {
        router.replace({ pathname: '/prenom', params: { next } });
      } else {
        router.dismissTo(next as Href);
      }
    } catch (error) {
      setCode('');
      submitted.current = '';
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const press = (key: string) => {
    if (key === '⌫') {
      setCode((value) => value.slice(0, -1));
      return;
    }
    setCode((value) => {
      if (value.length >= length) return value;
      const next = value + key;
      if (next.length === length) setTimeout(() => verify(next), 120);
      return next;
    });
  };

  const resend = async () => {
    if (wait > 0) return;
    try {
      const challenge = await api.requestOtp(params.phone);
      setWait(challenge.resend_in);
      sayText('Je t’ai envoyé un nouveau code sur WhatsApp.');
    } catch (error) {
      await sayError(error);
    }
  };

  const shown = `${local.slice(0, 2)} ${local.slice(2, 5)} ${local.slice(5, 7)} ${local.slice(7, 9)}`;

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.sand,
        paddingTop: insets.top,
        paddingHorizontal: 20,
        paddingBottom: insets.bottom,
        gap: 18,
      }}
    >
      <StatusBar style="dark" />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <BackButton />
        <StepDots total={3} current={2} />
        <ScreenSpeaker prompt="app.code.screen" />
      </View>

      <View>
        <T display w={700} size={30} lh={1.05} ls={-0.8}>
          Regarde ton WhatsApp
        </T>
        <T size={15} lh={1.4} color={colors.muted} style={{ marginTop: 6 }}>
          On a envoyé un code à {length} chiffres au{' '}
          <T w={700} size={15}>
            {shown}
          </T>
          .
        </T>
      </View>

      <View style={{ flexDirection: 'row', gap: 10 }}>
        {Array.from({ length }, (_, index) => (
          <View
            key={index}
            style={{
              flex: 1,
              height: length > 4 ? 64 : 80,
              borderRadius: 22,
              backgroundColor: colors.paper,
              borderWidth: 2,
              borderColor: index === code.length ? colors.light : code[index] ? colors.line : colors.lineSoft,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <T display w={800} size={length > 4 ? 30 : 38}>
              {code[index] ?? ''}
            </T>
          </View>
        ))}
      </View>

      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 10,
          backgroundColor: colors.lightSoft,
          borderRadius: 16,
          paddingVertical: 4,
          paddingLeft: 14,
          paddingRight: 4,
        }}
      >
        <Icon name="clock" size={20} color={colors.lightInk} />
        <Tap
          onPress={resend}
          disabled={wait > 0}
          style={{ flex: 1, minHeight: 44, justifyContent: 'center' }}
        >
          <T
            size={14}
            w={wait > 0 ? 400 : 700}
            color={colors.brown}
            style={wait > 0 ? undefined : { textDecorationLine: 'underline' }}
          >
            {wait > 0
              ? `Pas reçu ? Renvoyer dans ${formatDuration(wait)}`
              : 'Pas reçu ? Touche ici pour renvoyer le code'}
          </T>
        </Tap>
        <MiniSpeaker prompt="app.code.resend" label="Écouter : renvoyer le code" width={44} height={44} />
      </View>

      <View style={{ flex: 1 }} />

      <NumberPad onKey={press} />

      <PrimaryButton
        label="Continuer"
        bg={full ? colors.night : colors.line}
        fg={full ? colors.sand : colors.label}
        disabled={!full}
        loading={busy}
        onPress={() => verify(code)}
      />

      <SayBubble top={insets.top + 64} />
    </View>
  );
}
