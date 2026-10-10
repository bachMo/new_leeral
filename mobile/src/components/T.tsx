import { Text, type TextProps, type TextStyle } from 'react-native';

import { colors, fonts } from '@/lib/theme';

type Weight = 400 | 500 | 600 | 700 | 800;

export const MAX_FONT_SCALE = 1.2;

type Props = TextProps & {
  display?: boolean;
  w?: Weight;
  size?: number;
  color?: string;
  lh?: number;
  ls?: number;
  upper?: boolean;
  center?: boolean;
};

function family(display: boolean, weight: Weight): string {
  if (display) return weight >= 800 ? fonts.display800 : fonts.display700;
  if (weight >= 800) return fonts.body800;
  if (weight >= 700) return fonts.body700;
  if (weight >= 600) return fonts.body600;
  if (weight >= 500) return fonts.body500;
  return fonts.body400;
}

export function T({
  display = false,
  w = 400,
  size = 16,
  color = colors.night,
  lh,
  ls,
  upper,
  center,
  style,
  maxFontSizeMultiplier = MAX_FONT_SCALE,
  ...rest
}: Props) {
  const base: TextStyle = {
    fontFamily: family(display, w),
    fontSize: size,
    color,
    lineHeight: lh ? Math.round(size * lh) : undefined,
    letterSpacing: ls,
    textTransform: upper ? 'uppercase' : undefined,
    textAlign: center ? 'center' : undefined,
  };
  return <Text {...rest} maxFontSizeMultiplier={maxFontSizeMultiplier} style={[base, style]} />;
}
