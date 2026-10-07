import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  View,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path, Rect } from 'react-native-svg';

import { useVoice } from '@/lib/voice';
import { colors } from '@/lib/theme';

import { Icon, type IconName } from './Icon';
import { T } from './T';

export function useInsets() {
  const insets = useSafeAreaInsets();
  return { top: Math.max(insets.top, 20) + 12, bottom: Math.max(insets.bottom, 8) + 16 };
}

export function useScreenVoice() {
  const voice = useVoice();
  const { hush } = voice;
  useFocusEffect(
    useCallback(() => {
      return () => hush();
    }, [hush]),
  );
  return voice;
}

type TapProps = PressableProps & { style?: StyleProp<ViewStyle>; children?: ReactNode };

export function Tap({ style, children, disabled, ...rest }: TapProps) {
  return (
    <Pressable
      {...rest}
      disabled={disabled}
      style={({ pressed }) => [style, pressed && !disabled ? styles.pressed : null]}
    >
      {children}
    </Pressable>
  );
}

export function Logo({ size = 36, inverted = false }: { size?: number; inverted?: boolean }) {
  const tile = inverted ? colors.sand : colors.night;
  const page = inverted ? colors.night : colors.sand;
  const fold = inverted ? '#2C4060' : colors.line;
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64">
      <Rect width={64} height={64} rx={18} fill={tile} />
      <Path d="M15 13h19l8 8v30H15z" fill={page} />
      <Path d="M34 13v8h8" fill={fold} />
      {inverted ? null : (
        <Path
          d="M20.5 29h14M20.5 35h14M20.5 41h9"
          stroke={colors.night}
          strokeWidth={2.6}
          strokeLinecap="round"
          opacity={0.3}
        />
      )}
      <Path
        d="M46.5 28.5a7.5 7.5 0 0 1 0 11"
        stroke={colors.light}
        strokeWidth={3.6}
        fill="none"
        strokeLinecap="round"
      />
      <Path
        d="M50.5 23a14 14 0 0 1 0 22"
        stroke={colors.light}
        strokeWidth={3.6}
        fill="none"
        strokeLinecap="round"
      />
    </Svg>
  );
}

type HaloProps = {
  size: number;
  inset: number;
  core: number;
  color?: string;
  outer?: number;
  middle?: number;
  coreStyle?: StyleProp<ViewStyle>;
  children?: ReactNode;
};

export function Halo({
  size,
  inset,
  core,
  color = colors.light,
  outer = 0.12,
  middle = 0.22,
  coreStyle,
  children,
}: HaloProps) {
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <View
        style={[StyleSheet.absoluteFill, { borderRadius: size / 2, backgroundColor: color, opacity: outer }]}
      />
      <View
        style={{
          position: 'absolute',
          top: inset,
          left: inset,
          right: inset,
          bottom: inset,
          borderRadius: size / 2,
          backgroundColor: color,
          opacity: middle,
        }}
      />
      <View
        style={[
          {
            width: core,
            height: core,
            borderRadius: core / 2,
            backgroundColor: color,
            alignItems: 'center',
            justifyContent: 'center',
          },
          coreStyle,
        ]}
      >
        {children}
      </View>
    </View>
  );
}

type RoundProps = {
  icon: IconName;
  label: string;
  onPress?: () => void;
  dark?: boolean;
  size?: number;
  iconSize?: number;
};

export function RoundButton({ icon, label, onPress, dark = false, size = 44, iconSize = 20 }: RoundProps) {
  return (
    <Tap
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={[
        styles.round,
        { width: size, height: size, borderRadius: size / 2 },
        dark ? styles.roundDark : styles.roundPaper,
      ]}
    >
      <Icon name={icon} size={iconSize} color={dark ? colors.sand : colors.night} />
    </Tap>
  );
}

export function BackButton({
  dark = false,
  close = false,
  label,
}: {
  dark?: boolean;
  close?: boolean;
  label?: string;
}) {
  return (
    <RoundButton
      icon={close ? 'close' : 'back'}
      label={label ?? (close ? 'Fermer' : 'Retour')}
      dark={dark}
      onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))}
    />
  );
}

export function ScreenSpeaker({ prompt, dark = false }: { prompt: string; dark?: boolean }) {
  const { say } = useVoice();
  return (
    <RoundButton
      icon="speaker"
      iconSize={22}
      dark={dark}
      label="Écouter l'explication de cet écran"
      onPress={() => say(prompt)}
    />
  );
}

type MiniSpeakerProps = {
  prompt?: string;
  onPress?: () => void;
  color?: string;
  label: string;
  width?: number;
  height?: number;
  opacity?: number;
  style?: StyleProp<ViewStyle>;
};

export function MiniSpeaker({
  prompt,
  onPress,
  color = colors.night,
  label,
  width = 36,
  height = 40,
  opacity = 0.55,
  style,
}: MiniSpeakerProps) {
  const { say } = useVoice();
  return (
    <Tap
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={4}
      onPress={onPress ?? (() => prompt && say(prompt))}
      style={[
        { width, height, borderRadius: 12, alignItems: 'center', justifyContent: 'center', opacity },
        style,
      ]}
    >
      <Icon name="speakerSmall" size={19} color={color} />
    </Tap>
  );
}

function SpeakingBars({ color, active }: { color: string; active: boolean }) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!active) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 420,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 420,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, pulse]);
  const heights = [10, 20, 14, 8];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3, height: 22 }}>
      {heights.map((height, index) => (
        <Animated.View
          key={index}
          style={{
            width: 4,
            height,
            borderRadius: 2,
            backgroundColor: color,
            transform: [
              {
                scaleY: pulse.interpolate({
                  inputRange: [0, 1],
                  outputRange: index % 2 ? [1, 0.55] : [0.6, 1.15],
                }),
              },
            ],
          }}
        />
      ))}
    </View>
  );
}

export function SayBubble({
  light = false,
  top,
  bottom,
}: {
  light?: boolean;
  top?: number;
  bottom?: number;
}) {
  const { message, speaking, hush } = useVoice();
  if (!message) return null;
  return (
    <View
      accessibilityRole="alert"
      style={[
        styles.bubble,
        { top, bottom, backgroundColor: light ? colors.sand : colors.night },
        light ? styles.bubbleShadowLight : styles.bubbleShadowDark,
      ]}
    >
      <SpeakingBars color={light ? colors.lightDeep : colors.light} active={speaking} />
      <View style={{ flex: 1, gap: 2 }}>
        <T w={700} size={11} ls={1.2} upper color={light ? colors.lightInk : colors.light}>
          Leeral te dit
        </T>
        <T size={15} lh={1.4} color={light ? colors.night : colors.sand}>
          {message}
        </T>
      </View>
      <Tap
        accessibilityRole="button"
        accessibilityLabel="Arrêter le message"
        onPress={hush}
        style={[styles.bubbleClose, { backgroundColor: light ? colors.sandDark : 'rgba(246,240,228,0.1)' }]}
      >
        <Icon name="close" size={16} strokeWidth={2.4} color={light ? colors.night : colors.sand} />
      </Tap>
    </View>
  );
}

type PrimaryProps = {
  label: string;
  onPress?: () => void;
  height?: number;
  bg?: string;
  fg?: string;
  disabled?: boolean;
  loading?: boolean;
  size?: number;
  left?: ReactNode;
  right?: ReactNode;
  radius?: number;
  style?: StyleProp<ViewStyle>;
};

export function PrimaryButton({
  label,
  onPress,
  height = 62,
  bg = colors.night,
  fg = colors.sand,
  disabled = false,
  loading = false,
  size = 19,
  left,
  right,
  radius,
  style,
}: PrimaryProps) {
  return (
    <Tap
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        {
          height,
          borderRadius: radius ?? height / 2,
          backgroundColor: bg,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 10,
        },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : left}
      <T display w={700} size={size} color={fg}>
        {label}
      </T>
      {loading ? null : right}
    </Tap>
  );
}

export function StepDots({ total, current }: { total: number; current: number }) {
  return (
    <View style={{ flexDirection: 'row', gap: 6 }} accessibilityLabel={`Étape ${current} sur ${total}`}>
      {Array.from({ length: total }, (_, index) => (
        <View
          key={index}
          style={{
            width: 28,
            height: 6,
            borderRadius: 3,
            backgroundColor: index < current ? colors.light : colors.line,
          }}
        />
      ))}
    </View>
  );
}

const PAD = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '⌫'];

export function NumberPad({ onKey }: { onKey: (key: string) => void }) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {PAD.map((key, index) => (
        <Tap
          key={index}
          accessibilityRole="button"
          accessibilityLabel={key === '⌫' ? 'Effacer' : key || 'vide'}
          disabled={!key}
          onPress={() => key && onKey(key)}
          style={{
            width: '31.5%',
            flexGrow: 1,
            height: 60,
            borderRadius: 18,
            backgroundColor: key ? colors.paper : 'transparent',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <T display w={700} size={26}>
            {key}
          </T>
        </Tap>
      ))}
    </View>
  );
}

export function Waveform({
  bars,
  progress = 0,
  active,
  inactive,
  width = 3.5,
  gap = 3,
  height = 40,
}: {
  bars: number[];
  progress?: number;
  active: string;
  inactive: string;
  width?: number;
  gap?: number;
  height?: number;
}) {
  const lit = Math.round(bars.length * Math.min(1, Math.max(0, progress)));
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap, height }}>
      {bars.map((bar, index) => (
        <View
          key={index}
          style={{ width, height: bar, borderRadius: 2, backgroundColor: index < lit ? active : inactive }}
        />
      ))}
    </View>
  );
}

export function Loading({ dark = false }: { dark?: boolean }) {
  return (
    <View
      style={{
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: dark ? colors.night : colors.sand,
      }}
    >
      <ActivityIndicator color={dark ? colors.light : colors.night} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  pressed: { opacity: 0.72 },
  round: { alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  roundPaper: { backgroundColor: colors.paper, borderWidth: 1, borderColor: colors.line },
  roundDark: { backgroundColor: 'rgba(246,240,228,0.08)' },
  bubble: {
    position: 'absolute',
    left: 12,
    right: 12,
    borderRadius: 22,
    paddingVertical: 12,
    paddingLeft: 14,
    paddingRight: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    zIndex: 50,
  },
  bubbleShadowDark: {
    shadowColor: colors.night,
    shadowOpacity: 0.38,
    shadowRadius: 17,
    shadowOffset: { width: 0, height: 14 },
    elevation: 12,
  },
  bubbleShadowLight: {
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 17,
    shadowOffset: { width: 0, height: 14 },
    elevation: 12,
  },
  bubbleClose: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});
