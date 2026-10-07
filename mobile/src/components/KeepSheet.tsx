import { Modal, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/lib/theme';
import { useVoice } from '@/lib/voice';

import { Icon, type IconName } from './Icon';
import { T } from './T';
import { MiniSpeaker, RoundButton, SayBubble, Tap } from './ui';

function Benefit({ icon, label }: { icon: IconName; label: string }) {
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.sand,
        borderRadius: 18,
        paddingVertical: 12,
        paddingHorizontal: 10,
        gap: 8,
      }}
    >
      <Icon name={icon} size={22} color={colors.lightInk} />
      <T w={600} size={13} lh={1.3}>
        {label}
      </T>
    </View>
  );
}

type Props = { visible: boolean; title: string; onKeep: () => void; onDismiss: () => void };

export function KeepSheet({ visible, onKeep, onDismiss }: Props) {
  const insets = useSafeAreaInsets();
  const { say, hush } = useVoice();
  const close = () => {
    hush();
    onDismiss();
  };
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={close} statusBarTranslucent>
      <Pressable
        accessibilityLabel="Fermer"
        onPress={close}
        style={{ flex: 1, backgroundColor: 'rgba(18,35,59,0.55)' }}
      />
      <View
        accessibilityRole="none"
        accessibilityLabel="Garder ce document"
        style={{
          backgroundColor: colors.paper,
          borderTopLeftRadius: 32,
          borderTopRightRadius: 32,
          paddingTop: 12,
          paddingHorizontal: 20,
          paddingBottom: 28 + insets.bottom,
          gap: 18,
        }}
      >
        <View
          style={{ alignSelf: 'center', width: 44, height: 5, borderRadius: 3, backgroundColor: colors.line }}
        />
        <View style={{ flexDirection: 'row', gap: 14, alignItems: 'flex-start' }}>
          <View style={{ flex: 1 }}>
            <T display w={700} size={26} lh={1.1} ls={-0.5}>
              Garder ce document ?
            </T>
            <T size={15} lh={1.45} color={colors.muted} style={{ marginTop: 6 }}>
              Sans compte, il disparaît quand tu fermes Leeral.
            </T>
          </View>
          <RoundButton
            icon="speaker"
            iconSize={22}
            label="Écouter l'explication"
            onPress={() => say('app.keep.screen')}
          />
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Benefit icon="retry" label="Réécouter quand tu veux" />
          <Benefit icon="calendar" label="Retrouver les dates" />
          <Benefit icon="bookBare" label="Apprendre ses mots" />
        </View>
        <View style={{ gap: 8 }}>
          <View>
            <Tap
              accessibilityRole="button"
              onPress={() => {
                hush();
                onKeep();
              }}
              style={{
                height: 62,
                borderRadius: 31,
                backgroundColor: colors.night,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <T display w={700} size={18} color={colors.sand}>
                Oui, garder
              </T>
              <T size={12.5} color={colors.onNightMuted}>
                Juste ton numéro, 30 secondes
              </T>
            </Tap>
            <MiniSpeaker
              prompt="app.keep.yes"
              label="Écouter : oui, garder"
              color={colors.sand}
              style={{ position: 'absolute', right: 6, top: 11 }}
            />
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
            <Tap
              accessibilityRole="button"
              onPress={close}
              style={{ height: 52, paddingHorizontal: 16, justifyContent: 'center' }}
            >
              <T w={700} size={15}>
                Non merci
              </T>
            </Tap>
            <MiniSpeaker prompt="app.keep.no" label="Écouter : non merci" width={44} height={44} />
          </View>
        </View>
      </View>
      <SayBubble light top={insets.top + 72} />
    </Modal>
  );
}
