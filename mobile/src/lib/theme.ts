export const colors = {
  night: '#12233B',
  nightDeep: '#0B1626',
  nightBox: '#1B2A40',
  light: '#F4A62A',
  lightDeep: '#B87714',
  lightInk: '#8A5A08',
  lightSoft: '#FCE7C2',
  sand: '#F6F0E4',
  sandDark: '#E9DFCB',
  paper: '#FFFDF8',
  line: '#E3D6BD',
  lineSoft: '#EFE6D3',
  rowLine: '#F1E9DA',
  river: '#17756A',
  riverSoft: '#D3EAE5',
  riverInk: '#1F4D46',
  riverGlow: '#7FD1C4',
  clay: '#B5432A',
  claySoft: '#F6D9CF',
  clayInk: '#8F2F18',
  adminSoft: '#DDE2EA',
  muted: '#4E5967',
  label: '#6A5A3C',
  brown: '#5C4A26',
  onNightMuted: '#C9C1B0',
  placeholder: '#B9AE98',
  docInk: '#2A3442',
  docMuted: '#6B7480',
  white: '#FFFFFF',
} as const;

export const fonts = {
  display700: 'BricolageGrotesque_700Bold',
  display800: 'BricolageGrotesque_800ExtraBold',
  body400: 'Figtree_400Regular',
  body500: 'Figtree_500Medium',
  body600: 'Figtree_600SemiBold',
  body700: 'Figtree_700Bold',
  body800: 'Figtree_800ExtraBold',
} as const;

export type CategoryCode = 'health' | 'money' | 'school' | 'admin' | 'other';

export const categoryStyle: Record<
  CategoryCode,
  { label: string; dot: string; tint: string; ink: string; icon: string }
> = {
  health: {
    label: 'Santé',
    dot: colors.clay,
    tint: colors.claySoft,
    ink: colors.clayInk,
    icon: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z',
  },
  money: {
    label: 'Argent',
    dot: colors.light,
    tint: colors.lightSoft,
    ink: colors.lightInk,
    icon: 'M3 7h18v11H3zM3 11h18M7 15h3',
  },
  school: {
    label: 'École',
    dot: colors.river,
    tint: colors.riverSoft,
    ink: colors.riverInk,
    icon: 'M2 9l10-5 10 5-10 5zM6 11v5c3.5 2 8.5 2 12 0v-5',
  },
  admin: {
    label: 'Administration',
    dot: colors.night,
    tint: colors.adminSoft,
    ink: colors.night,
    icon: 'M4 21h16M5 21V10l7-5 7 5v11M9 21v-6h6v6',
  },
  other: {
    label: 'Autre',
    dot: colors.placeholder,
    tint: colors.sandDark,
    ink: colors.label,
    icon: 'M7 3h7l5 5v13H7zM14 3v5h5',
  },
};
