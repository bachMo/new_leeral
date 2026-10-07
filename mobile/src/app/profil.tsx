import { router, useFocusEffect } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Alert, Linking, Platform, ScrollView, View } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { SUPPORT_WHATSAPP } from '@/lib/config';
import { LANGUAGE_NAMES, longDate, phoneDisplay } from '@/lib/format';
import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';

function confirmAction(title: string, message: string, action: string): Promise<boolean> {
  if (Platform.OS === 'web') return Promise.resolve(globalThis.confirm?.(`${title}\n${message}`) ?? true);
  return new Promise((resolve) =>
    Alert.alert(title, message, [
      { text: 'Non', style: 'cancel', onPress: () => resolve(false) },
      { text: action, style: 'destructive', onPress: () => resolve(true) },
    ]),
  );
}

function Row({
  icon,
  label,
  value,
  prompt,
  onPress,
  last,
}: {
  icon: IconName;
  label: string;
  value: string;
  prompt: string;
  onPress: () => void;
  last?: boolean;
}) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        borderBottomWidth: last ? 0 : 1,
        borderBottomColor: colors.rowLine,
      }}
    >
      <Tap
        accessibilityRole="button"
        onPress={onPress}
        style={{
          flex: 1,
          minHeight: 64,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 14,
          paddingLeft: 16,
          paddingRight: 4,
        }}
      >
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
          <Icon name={icon} size={20} />
        </View>
        <T w={700} size={16} style={{ flex: 1 }}>
          {label}
        </T>
        <T w={700} size={14} color={colors.muted}>
          {value}
        </T>
      </Tap>
      <MiniSpeaker
        prompt={prompt}
        label={`Écouter : ${label}`}
        width={44}
        height={48}
        style={{ marginRight: 6 }}
      />
    </View>
  );
}

export default function ProfileScreen() {
  const insets = useInsets();
  const { me, language, logout, refreshMe } = useSession();
  const { speed, setSpeed, sayError, sayText } = useScreenVoice();
  const [count, setCount] = useState<number | null>(null);
  const [busy, setBusy] = useState<'erase' | 'logout' | null>(null);

  useFocusEffect(
    useCallback(() => {
      refreshMe();
      api
        .documents(50)
        .then((page) => setCount(page.items.length))
        .catch(() => undefined);
    }, [refreshMe]),
  );

  const name = me?.user.first_name ?? 'Mon compte';
  const plus = me?.plan.code === 'leeral_plus';
  const usage = me?.usage;

  const erase = async () => {
    if (
      !(await confirmAction(
        'Effacer tous mes documents ?',
        'Tes documents seront supprimés de Leeral. On ne peut pas revenir en arrière.',
        'Effacer',
      ))
    )
      return;
    setBusy('erase');
    try {
      const page = await api.documents(50);
      for (const doc of page.items) await api.deleteDocument(doc.id);
      setCount(0);
      sayText('Tous tes documents sont effacés.');
    } catch (error) {
      await sayError(error);
    } finally {
      setBusy(null);
    }
  };

  const signOut = async () => {
    setBusy('logout');
    try {
      await logout();
      router.dismissTo('/accueil');
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.sand }}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          paddingTop: insets.top,
          paddingHorizontal: 20,
          paddingBottom: insets.bottom,
          gap: 16,
        }}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <BackButton />
          <T display w={700} size={22} style={{ flex: 1 }}>
            Mon compte
          </T>
          <ScreenSpeaker prompt="app.profile.screen" />
        </View>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <View
            style={{
              width: 68,
              height: 68,
              borderRadius: 34,
              backgroundColor: colors.night,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <T display w={800} size={28} color={colors.light}>
              {name.charAt(0).toUpperCase()}
            </T>
          </View>
          <View style={{ flex: 1 }}>
            <T display w={800} size={26} ls={-0.5} numberOfLines={1}>
              {name}
            </T>
            <T size={14} color={colors.muted}>
              {phoneDisplay(me?.user.phone_number ?? null)}
            </T>
          </View>
        </View>

        <View
          style={{
            backgroundColor: colors.lightSoft,
            borderRadius: 22,
            flexDirection: 'row',
            alignItems: 'center',
            paddingRight: 4,
          }}
        >
          <Tap
            accessibilityRole="button"
            onPress={() => router.push('/plus')}
            style={{
              flex: 1,
              paddingVertical: 14,
              paddingLeft: 16,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <View style={{ flex: 1 }}>
              <T w={800} size={16}>
                {plus ? 'Leeral+' : 'Formule gratuite'}
              </T>
              <T size={13} color={colors.brown} style={{ marginTop: 2 }}>
                {plus && me?.plan.expires_at
                  ? `Jusqu'au ${longDate(me.plan.expires_at)}`
                  : usage
                    ? `Écrire pour moi : ${usage.writings_used} sur ${usage.writings_limit} ce mois`
                    : ' '}
              </T>
            </View>
            <View
              style={{
                height: 40,
                paddingHorizontal: 14,
                borderRadius: 20,
                backgroundColor: colors.night,
                justifyContent: 'center',
              }}
            >
              <T w={700} size={14} color={colors.light}>
                {plus ? 'Renouveler' : 'Leeral+'}
              </T>
            </View>
          </Tap>
          <MiniSpeaker prompt="app.profile.plan" label="Écouter : ma formule" width={40} height={48} />
        </View>

        <View style={{ backgroundColor: colors.paper, borderRadius: 22, overflow: 'hidden' }}>
          <Row
            icon="globeRow"
            label="Langue"
            value={LANGUAGE_NAMES[language]}
            prompt="app.profile.language"
            onPress={() => router.push('/langue?change=1')}
          />
          <Row
            icon="speed"
            label="Vitesse de la voix"
            value={speed === 'slow' ? 'Lente' : 'Normale'}
            prompt="app.profile.speed"
            onPress={() => setSpeed(speed === 'slow' ? 'normal' : 'slow')}
          />
          <Row
            icon="docRow"
            label="Mes documents"
            value={count === null ? '' : String(count)}
            prompt="app.profile.documents"
            onPress={() => router.navigate('/documents')}
          />
          <Row
            icon="help"
            label="Aide sur WhatsApp"
            value=""
            prompt="app.profile.help"
            last
            onPress={() => Linking.openURL(`https://wa.me/${SUPPORT_WHATSAPP}`).catch(() => undefined)}
          />
        </View>

        <View style={{ flex: 1 }} />

        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <Tap
              accessibilityRole="button"
              onPress={erase}
              disabled={busy !== null}
              style={{
                flex: 1,
                height: 52,
                borderRadius: 18,
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              {busy === 'erase' ? (
                <ActivityIndicator color={colors.clayInk} />
              ) : (
                <Icon name="trash" size={18} color={colors.clayInk} />
              )}
              <T w={700} size={15} color={colors.clayInk}>
                Effacer tous mes documents
              </T>
            </Tap>
            <MiniSpeaker
              prompt="app.profile.erase"
              label="Écouter : effacer mes documents"
              width={44}
              height={48}
            />
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <Tap
              accessibilityRole="button"
              onPress={signOut}
              disabled={busy !== null}
              style={{
                flex: 1,
                height: 52,
                borderRadius: 18,
                backgroundColor: colors.paper,
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              {busy === 'logout' ? (
                <ActivityIndicator color={colors.night} />
              ) : (
                <Icon name="logout" size={18} />
              )}
              <T w={700} size={15}>
                Me déconnecter
              </T>
            </Tap>
            <MiniSpeaker
              prompt="app.profile.logout"
              label="Écouter : me déconnecter"
              width={44}
              height={48}
            />
          </View>
        </View>
      </ScrollView>
      <SayBubble top={insets.top + 64} />
    </View>
  );
}
