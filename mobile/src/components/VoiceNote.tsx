import { View } from 'react-native';

import { formatDuration } from '@/lib/audio';
import { colors } from '@/lib/theme';

import { Icon } from './Icon';
import { T } from './T';
import { Tap, Waveform } from './ui';

type Props = {
  bars: number[];
  playing: boolean;
  progress: number;
  duration: number | null;
  onPress: () => void;
  onSeek?: (fraction: number) => void;
  tone: 'mine' | 'leeral';
  label: string;
};

export function VoiceNote({ bars, playing, progress, duration, onPress, onSeek, tone, label }: Props) {
  const mine = tone === 'mine';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <Tap
        accessibilityRole="button"
        accessibilityLabel={label}
        onPress={onPress}
        style={{
          width: mine ? 36 : 44,
          height: mine ? 36 : 44,
          borderRadius: 22,
          backgroundColor: mine ? colors.night : colors.light,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Icon
          name={playing ? 'pause' : 'play'}
          size={mine ? 12 : 14}
          color={mine ? colors.light : colors.night}
        />
      </Tap>
      <Waveform
        bars={bars}
        progress={progress}
        onSeek={onSeek}
        label={`${label} : avancer ou reculer`}
        width={3}
        gap={2.5}
        height={mine ? 22 : 24}
        active={mine ? colors.night : colors.light}
        inactive={mine ? colors.lightInk : 'rgba(246,240,228,0.5)'}
      />
      {duration ? (
        <T w={600} size={12} color={mine ? colors.brown : colors.onNightMuted}>
          {formatDuration(duration)}
        </T>
      ) : null}
    </View>
  );
}

export function barsFor(seed: string, count: number, min = 8, max = 22): number[] {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  return Array.from({ length: count }, (_, index) => {
    hash = (hash * 1103515245 + 12345 + index) >>> 0;
    return min + (hash % (max - min + 1));
  });
}
