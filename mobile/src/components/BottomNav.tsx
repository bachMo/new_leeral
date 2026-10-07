import { router, type Href } from 'expo-router';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/lib/theme';

import { Icon, type IconName } from './Icon';
import { T } from './T';
import { Tap } from './ui';

type Tab = 'home' | 'documents' | 'write' | 'learn';

const TABS: { id: Tab; label: string; icon: IconName; href: Href; push?: boolean }[] = [
  { id: 'home', label: 'Accueil', icon: 'home', href: '/accueil' },
  { id: 'documents', label: 'Documents', icon: 'file', href: '/documents' },
  { id: 'write', label: 'Écrire', icon: 'penBare', href: '/ecrire' },
  { id: 'learn', label: 'Apprendre', icon: 'bookBare', href: '/apprendre', push: true },
];

export function BottomNav({ active }: { active: Tab }) {
  const insets = useSafeAreaInsets();
  return (
    <View
      accessibilityRole="tablist"
      style={{
        height: 78 + Math.max(insets.bottom - 8, 0),
        paddingTop: 6,
        paddingHorizontal: 8,
        paddingBottom: 14 + Math.max(insets.bottom - 8, 0),
        backgroundColor: colors.paper,
        borderTopWidth: 1,
        borderTopColor: colors.line,
        flexDirection: 'row',
      }}
    >
      {TABS.map((tab) => {
        const current = tab.id === active;
        return (
          <Tap
            key={tab.id}
            accessibilityRole="tab"
            accessibilityState={{ selected: current }}
            onPress={() => {
              if (current) return;
              if (tab.push) router.push(tab.href);
              else router.navigate(tab.href);
            }}
            style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 }}
          >
            <View
              style={{
                width: 52,
                height: 30,
                borderRadius: 15,
                backgroundColor: current ? colors.lightSoft : 'transparent',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Icon name={tab.icon} size={20} color={current ? colors.night : colors.muted} />
            </View>
            <T w={current ? 700 : 600} size={12} color={current ? colors.night : colors.muted}>
              {tab.label}
            </T>
          </Tap>
        );
      })}
    </View>
  );
}
