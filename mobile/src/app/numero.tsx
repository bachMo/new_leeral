import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
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
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { colors } from '@/lib/theme';

const LENGTH = 9;

function formatLocal(digits: string): string {
  const pad = (digits + '_'.repeat(LENGTH)).slice(0, LENGTH);
  return `${pad.slice(0, 2)} ${pad.slice(2, 5)} ${pad.slice(5, 7)} ${pad.slice(7, 9)}`;
}

export default function PhoneScreen() {
  const { next } = useLocalSearchParams<{ next?: string }>();
  const insets = useInsets();
  const { sayError } = useScreenVoice();
  const [digits, setDigits] = useState('');
  const [busy, setBusy] = useState(false);
  const full = digits.length === LENGTH;

  const press = (key: string) => {
    if (key === '⌫') setDigits((value) => value.slice(0, -1));
    else setDigits((value) => (value.length < LENGTH ? value + key : value));
  };

  const go = async () => {
    if (!full) return;
    setBusy(true);
    const phone = `+221${digits}`;
    try {
      const challenge = await api.requestOtp(phone);
      router.push({
        pathname: '/code',
        params: {
          phone: challenge.phone_number,
          local: digits,
          length: String(challenge.code_length),
          resend: String(challenge.resend_in),
          next: next ?? '',
        },
      });
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

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
        <StepDots total={3} current={1} />
        <ScreenSpeaker prompt="app.phone.screen" />
      </View>

      <View>
        <T display w={700} size={30} lh={1.05} ls={-0.8}>
          Ton numéro de téléphone
        </T>
        <T size={15} lh={1.4} color={colors.muted} style={{ marginTop: 6 }}>
          Pas de mot de passe. On t&apos;envoie un code sur WhatsApp.
        </T>
      </View>

      <View>
        <View
          style={{
            height: 76,
            borderRadius: 22,
            backgroundColor: colors.paper,
            borderWidth: 2,
            borderColor: full ? colors.river : colors.light,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 12,
            paddingHorizontal: 16,
          }}
        >
          <T
            w={700}
            size={18}
            color={colors.muted}
            style={{ paddingRight: 12, borderRightWidth: 1, borderRightColor: colors.line }}
          >
            +221
          </T>
          <T
            display
            w={700}
            size={28}
            ls={1}
            color={digits ? colors.night : colors.placeholder}
            style={{ flex: 1, fontVariant: ['tabular-nums'] }}
          >
            {formatLocal(digits)}
          </T>
        </View>
        <MiniSpeaker
          prompt="app.phone.field"
          label="Écouter : mon numéro"
          style={{ position: 'absolute', right: 6, top: 18 }}
        />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: -8 }}>
        <Icon name="lock" size={16} color={colors.muted} />
        <T size={13} color={colors.muted}>
          Nouveau ou déjà inscrit : c&apos;est pareil.
        </T>
      </View>

      <View style={{ flex: 1 }} />

      <NumberPad onKey={press} />

      <View>
        <PrimaryButton
          label="Recevoir mon code"
          bg={full ? colors.night : colors.line}
          fg={full ? colors.sand : colors.label}
          disabled={!full}
          loading={busy}
          onPress={go}
          right={<Icon name="arrow" size={22} color={full ? colors.sand : colors.label} />}
        />
        <MiniSpeaker
          prompt="app.phone.go"
          label="Écouter : recevoir mon code"
          color={full ? colors.sand : colors.label}
          style={{ position: 'absolute', right: 6, top: 11 }}
        />
      </View>

      <SayBubble top={insets.top + 64} />
    </View>
  );
}
