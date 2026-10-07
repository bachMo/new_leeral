import { BricolageGrotesque_700Bold } from '@expo-google-fonts/bricolage-grotesque/700Bold';
import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque/800ExtraBold';
import { Figtree_400Regular } from '@expo-google-fonts/figtree/400Regular';
import { Figtree_500Medium } from '@expo-google-fonts/figtree/500Medium';
import { Figtree_600SemiBold } from '@expo-google-fonts/figtree/600SemiBold';
import { Figtree_700Bold } from '@expo-google-fonts/figtree/700Bold';
import { Figtree_800ExtraBold } from '@expo-google-fonts/figtree/800ExtraBold';
import { useFonts } from 'expo-font';
import { router, Stack, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, type ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { Offline } from '@/components/Offline';
import { Loading } from '@/components/ui';
import { SessionProvider, useSession } from '@/lib/session';
import { colors } from '@/lib/theme';
import { VoiceProvider } from '@/lib/voice';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

const PUBLIC_ROUTES = new Set(['langue', 'index']);

function SessionGuard() {
  const { ready, me, offline } = useSession();
  const segments = useSegments();
  const current = segments[0] ?? 'index';

  useEffect(() => {
    if (ready && !me && !offline && !PUBLIC_ROUTES.has(current)) router.replace('/langue');
  }, [ready, me, offline, current]);

  return null;
}

function SessionGate({ children }: { children: ReactNode }) {
  const { ready, offline } = useSession();
  if (!ready) return <Loading dark />;
  if (offline) return <Offline />;
  return <>{children}</>;
}

export default function RootLayout() {
  const [loaded, failed] = useFonts({
    BricolageGrotesque_700Bold,
    BricolageGrotesque_800ExtraBold,
    Figtree_400Regular,
    Figtree_500Medium,
    Figtree_600SemiBold,
    Figtree_700Bold,
    Figtree_800ExtraBold,
  });

  useEffect(() => {
    if (loaded || failed) SplashScreen.hideAsync().catch(() => undefined);
  }, [loaded, failed]);

  if (!loaded && !failed) return null;

  return (
    <SafeAreaProvider>
      <SessionProvider>
        <VoiceProvider>
          <SessionGuard />
          <SessionGate>
            <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.sand } }}>
              <Stack.Screen name="accueil" options={{ animation: 'none' }} />
              <Stack.Screen name="documents" options={{ animation: 'none' }} />
              <Stack.Screen name="ecrire" options={{ animation: 'none' }} />
              <Stack.Screen name="camera" options={{ contentStyle: { backgroundColor: colors.nightDeep } }} />
              <Stack.Screen name="lecture" options={{ contentStyle: { backgroundColor: colors.night } }} />
              <Stack.Screen name="langue" options={{ contentStyle: { backgroundColor: colors.night } }} />
              <Stack.Screen name="plus" options={{ contentStyle: { backgroundColor: colors.night } }} />
            </Stack>
          </SessionGate>
        </VoiceProvider>
      </SessionProvider>
    </SafeAreaProvider>
  );
}
