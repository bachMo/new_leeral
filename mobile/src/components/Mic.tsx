import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';

import { colors } from '@/lib/theme';

import { Icon } from './Icon';
import { Halo, Tap } from './ui';

type Props = {
  recording: boolean;
  busy?: boolean;
  onPress: () => void;
  size?: number;
  inset?: number;
  core?: number;
  iconSize?: number;
  idleLabel: string;
  recordingLabel?: string;
};

export function MicButton({
  recording,
  busy = false,
  onPress,
  size = 104,
  inset = 12,
  core = 64,
  iconSize = 28,
  idleLabel,
  recordingLabel = 'Envoyer',
}: Props) {
  const color = recording ? colors.clay : colors.light;
  return (
    <Tap
      accessibilityRole="button"
      accessibilityLabel={recording ? recordingLabel : idleLabel}
      onPress={onPress}
      disabled={busy}
    >
      <Halo size={size} inset={inset} core={core} color={color} outer={0.14} middle={0.26}>
        {busy ? (
          <ActivityIndicator color={colors.night} />
        ) : recording ? (
          <Icon name="send" size={iconSize - 2} color={colors.white} />
        ) : (
          <Icon name="mic" size={iconSize} color={colors.night} />
        )}
      </Halo>
    </Tap>
  );
}

const LIVE = [8, 16, 24, 12, 28, 20, 10, 18, 26, 14, 8, 20, 28, 16, 10, 22, 18, 8, 14, 24, 12, 18, 10, 8];

export function LiveBars({ color = colors.clay }: { color?: string }) {
  const [shift, setShift] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setShift((value) => (value + 1) % LIVE.length), 140);
    return () => clearInterval(timer);
  }, []);
  return (
    <View
      style={{ flexDirection: 'row', alignItems: 'center', gap: 3, height: 30 }}
      accessibilityLiveRegion="polite"
    >
      {LIVE.map((_, index) => (
        <View
          key={index}
          style={{
            width: 4,
            height: LIVE[(index + shift) % LIVE.length],
            borderRadius: 2,
            backgroundColor: color,
          }}
        />
      ))}
    </View>
  );
}
