import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { Modal, Share, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  MiniSpeaker,
  PrimaryButton,
  SayBubble,
  Screen,
  ScreenSpeaker,
  Tap,
  useInsets,
  useLayout,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { longDate, money, phoneDisplay } from '@/lib/format';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import type { Payment, Plan } from '@/lib/types';

export default function PlusScreen() {
  const insets = useInsets();
  const { fit } = useLayout();
  const { me, isGuest, refreshMe } = useSession();
  const { say, sayError } = useScreenVoice();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false);

  useFocusEffect(
    useCallback(() => {
      api
        .plans()
        .then(setPlans)
        .catch(() => undefined);
    }, []),
  );

  const free = plans.find((plan) => plan.code === 'free');
  const plus = plans.find((plan) => plan.code === 'leeral_plus');
  const price = plus?.price_xof ?? 500;
  const active = me?.plan.code === 'leeral_plus';

  const rows = [
    {
      label: 'Écrire pour moi',
      sub: 'CV, lettre, demande',
      free: `${free?.writings_per_month ?? 1} / mois`,
      plus: `${plus?.writings_per_month ?? 5} / mois`,
    },
    { label: 'Mots essentiels', sub: 'Les mots de base', free: 'Oui', plus: 'Oui' },
    { label: 'Mots de mes documents', sub: 'Apprendre le français', free: '—', plus: 'Oui' },
    {
      label: 'Exercices',
      sub: 'Séances par jour',
      free: free?.practice_per_day ? String(free.practice_per_day) : 'Illimité',
      plus: plus?.practice_per_day ? String(plus.practice_per_day) : 'Illimité',
    },
  ];

  const pay = async () => {
    if (isGuest) {
      router.push({ pathname: '/numero', params: { next: '/plus' } });
      return;
    }
    setBusy(true);
    try {
      setPayment(await api.checkout());
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const confirmPayment = async () => {
    if (!payment) return;
    setBusy(true);
    try {
      await api.simulatePayment(payment.public_token);
      setPayment(null);
      await refreshMe();
      say('app.plus.done');
    } catch (error) {
      setPayment(null);
      await sayError(error);
    } finally {
      setBusy(false);
    }
  };

  const askRelative = async () => {
    const phone = phoneDisplay(me?.user.phone_number ?? null);
    await Share.share({
      message: `Bonjour, peux-tu m'aider à payer Leeral+ (${money(price)} par mois) ? C'est l'application qui m'explique mes papiers dans ma langue.${phone ? ` Mon numéro : ${phone}.` : ''}`,
    }).catch(() => undefined);
  };

  const overlay = (
    <>
      <Modal visible={!!payment} transparent animationType="fade" onRequestClose={() => setPayment(null)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(11,22,38,0.7)', justifyContent: 'flex-end' }}>
          <View
            style={{
              backgroundColor: colors.paper,
              borderTopLeftRadius: 32,
              borderTopRightRadius: 32,
              padding: 20,
              paddingBottom: 28 + insets.bottom - 16,
              gap: 14,
            }}
          >
            <View
              style={{
                alignSelf: 'center',
                width: 44,
                height: 5,
                borderRadius: 3,
                backgroundColor: colors.line,
              }}
            />
            <T display w={700} size={24}>
              Paiement Wave
            </T>
            <T size={15} lh={1.45} color={colors.muted}>
              Paiement simulé pour la démo : aucun argent n&apos;est prélevé. Confirme pour activer Leeral+
              pendant 30 jours.
            </T>
            <View
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                backgroundColor: colors.sand,
                borderRadius: 16,
                padding: 14,
              }}
            >
              <T w={700} size={16}>
                Leeral+ · 1 mois
              </T>
              <T display w={800} size={18}>
                {money(payment?.amount_xof ?? price)}
              </T>
            </View>
            <PrimaryButton
              label="Confirmer le paiement"
              bg={colors.light}
              fg={colors.night}
              loading={busy}
              onPress={confirmPayment}
            />
            <Tap
              onPress={() => setPayment(null)}
              style={{ height: 48, alignItems: 'center', justifyContent: 'center' }}
            >
              <T w={700} size={15}>
                Annuler
              </T>
            </Tap>
          </View>
        </View>
      </Modal>

      <SayBubble light top={insets.top + 64} />
    </>
  );

  return (
    <Screen background={colors.night} overlay={overlay}>
      <StatusBar style="light" />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <BackButton dark close />
        <ScreenSpeaker prompt="app.plus.screen" dark />
      </View>

      <View>
        <T display w={800} size={fit(44)} ls={-1.5} lh={1} color={colors.sand} numberOfLines={1}>
          leeral
          <T display w={800} size={fit(44)} color={colors.light}>
            +
          </T>
        </T>
        <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6, marginTop: 10 }}>
          <T display w={800} size={fit(34)} color={colors.light}>
            {money(price)}
          </T>
          <T size={16} color={colors.onNightMuted}>
            par mois
          </T>
        </View>
      </View>

      <View
        style={{
          backgroundColor: 'rgba(23,117,106,0.22)',
          borderRadius: 18,
          paddingVertical: 12,
          paddingHorizontal: 14,
          flexDirection: 'row',
          gap: 10,
          alignItems: 'center',
        }}
      >
        <Icon name="check" size={22} strokeWidth={2.4} color={colors.riverGlow} />
        <T size={14.5} lh={1.35} color={colors.sand} style={{ flex: 1 }}>
          <T w={700} size={14.5} color={colors.sand}>
            Comprendre un document reste gratuit
          </T>
          , pour tout le monde, sans limite.
        </T>
      </View>

      <View style={{ borderRadius: 22, overflow: 'hidden', backgroundColor: 'rgba(246,240,228,0.06)' }}>
        <View style={{ flexDirection: 'row', paddingVertical: 12, paddingHorizontal: 14 }}>
          <View style={{ flex: 1.6 }}>
            <MiniSpeaker
              prompt="app.plus.table"
              label="Écouter : ce que contient Leeral+"
              color={colors.sand}
              width={36}
              height={36}
              style={{ marginLeft: -6, marginVertical: -8 }}
            />
          </View>
          <T w={700} size={12} ls={1} upper color={colors.onNightMuted} center style={{ flex: 1 }}>
            Gratuit
          </T>
          <T w={700} size={12} ls={1} upper color={colors.light} center style={{ flex: 1 }}>
            Leeral+
          </T>
        </View>
        {rows.map((row) => (
          <View
            key={row.label}
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              paddingVertical: 12,
              paddingHorizontal: 14,
              borderTopWidth: 1,
              borderTopColor: 'rgba(246,240,228,0.08)',
            }}
          >
            <View style={{ flex: 1.6 }}>
              <T w={700} size={15} color={colors.sand}>
                {row.label}
              </T>
              <T size={12.5} color={colors.onNightMuted}>
                {row.sub}
              </T>
            </View>
            <T size={14} color={colors.onNightMuted} center style={{ flex: 1 }}>
              {row.free}
            </T>
            <T w={800} size={14} color={colors.light} center style={{ flex: 1 }}>
              {row.plus}
            </T>
          </View>
        ))}
      </View>

      <View style={{ flexGrow: 1 }} />

      <View style={{ gap: 10 }}>
        {active ? (
          <View
            style={{
              height: 64,
              borderRadius: 32,
              backgroundColor: 'rgba(23,117,106,0.22)',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <T display w={700} size={18} color={colors.sand}>
              Leeral+ actif{me?.plan.expires_at ? ` jusqu'au ${longDate(me.plan.expires_at)}` : ''}
            </T>
          </View>
        ) : (
          <View>
            <PrimaryButton
              label={`Payer avec Wave · ${money(price)}`}
              height={64}
              bg={colors.light}
              fg={colors.night}
              loading={busy}
              onPress={pay}
            />
            <MiniSpeaker
              prompt="app.plus.pay"
              label="Écouter : payer avec Wave"
              color={colors.night}
              style={{ position: 'absolute', right: 6, top: 12 }}
            />
          </View>
        )}
        <View>
          <Tap
            accessibilityRole="button"
            onPress={askRelative}
            style={{
              height: 56,
              borderRadius: 28,
              backgroundColor: 'rgba(246,240,228,0.08)',
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            <Icon name="addUser" size={18} color={colors.sand} />
            <T w={700} size={15} color={colors.sand}>
              Un proche paie pour moi
            </T>
          </Tap>
          <MiniSpeaker
            prompt="app.plus.relative"
            label="Écouter : un proche paie pour moi"
            color={colors.sand}
            style={{ position: 'absolute', right: 6, top: 8 }}
          />
        </View>
        <T size={12.5} color={colors.onNightMuted} center>
          Pas de prélèvement automatique. Rappel 2 jours avant la fin.
        </T>
      </View>
    </Screen>
  );
}
