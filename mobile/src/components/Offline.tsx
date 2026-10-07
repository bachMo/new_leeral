import { useState } from 'react';
import { View } from 'react-native';

import { useSession } from '@/lib/session';
import { colors } from '@/lib/theme';

import { Icon } from './Icon';
import { T } from './T';
import { Logo, PrimaryButton } from './ui';

export function Offline() {
  const { refreshMe } = useSession();
  const [busy, setBusy] = useState(false);
  const retry = async () => {
    setBusy(true);
    await refreshMe();
    setBusy(false);
  };
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.night,
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        gap: 18,
      }}
    >
      <Logo size={64} inverted />
      <T display w={800} size={28} ls={-0.6} color={colors.sand} center>
        Pas de connexion
      </T>
      <T size={16} lh={1.45} color={colors.onNightMuted} center>
        Leeral n&apos;arrive pas à joindre le serveur. Vérifie ton internet, puis réessaie.
      </T>
      <PrimaryButton
        label="Réessayer"
        height={60}
        bg={colors.light}
        fg={colors.night}
        loading={busy}
        onPress={retry}
        left={<Icon name="retry" size={22} color={colors.night} />}
        style={{ alignSelf: 'stretch' }}
      />
    </View>
  );
}
