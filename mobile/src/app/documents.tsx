import { router, useFocusEffect, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, View } from 'react-native';

import { BottomNav } from '@/components/BottomNav';
import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import { SayBubble, ScreenSpeaker, Tap, useInsets, useScreenVoice } from '@/components/ui';
import { api } from '@/lib/api';
import { documentMeta, normalize, plural } from '@/lib/format';
import { useVoiceRecorder } from '@/lib/recorder';
import { useSession } from '@/lib/session';
import { categoryStyle, colors, type CategoryCode } from '@/lib/theme';

type Item = {
  key: string;
  title: string;
  meta: string;
  metaColor: string;
  category: CategoryCode;
  createdAt: number;
  href: Href;
};

const FILTERS: { id: 'all' | CategoryCode; label: string; dot: string; prompt: string }[] = [
  { id: 'all', label: 'Tout', dot: colors.placeholder, prompt: 'app.documents.all' },
  { id: 'health', label: 'Santé', dot: colors.clay, prompt: 'app.documents.health' },
  { id: 'money', label: 'Argent', dot: colors.light, prompt: 'app.documents.money' },
  { id: 'school', label: 'École', dot: colors.river, prompt: 'app.documents.school' },
  { id: 'admin', label: 'Administration', dot: colors.night, prompt: 'app.documents.admin' },
];

const DAY = 24 * 60 * 60 * 1000;

function groupLabel(createdAt: number): string {
  const age = Date.now() - createdAt;
  if (age < 7 * DAY) return 'Cette semaine';
  if (age < 31 * DAY) return 'Ce mois-ci';
  return 'Plus ancien';
}

export default function DocumentsScreen() {
  const insets = useInsets();
  const { isGuest } = useSession();
  const { say, sayError, sayText } = useScreenVoice();
  const recorder = useVoiceRecorder();
  const [items, setItems] = useState<Item[] | null>(null);
  const [filter, setFilter] = useState<'all' | CategoryCode>('all');
  const [query, setQuery] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        const [docs, writings] = await Promise.all([
          api
            .documents(50)
            .then((page) => page.items)
            .catch(() => []),
          isGuest ? Promise.resolve([]) : api.writings().catch(() => []),
        ]);
        const merged: Item[] = [
          ...docs.map((doc) => {
            const meta = documentMeta(doc);
            return {
              key: `d-${doc.id}`,
              title: doc.title ?? 'Document',
              meta: meta.text,
              metaColor: meta.color,
              category: (doc.category in categoryStyle ? doc.category : 'other') as CategoryCode,
              createdAt: new Date(doc.created_at).getTime(),
              href: (doc.status === 'ready' ? `/explication/${doc.id}` : `/lecture?doc=${doc.id}`) as Href,
            };
          }),
          ...writings.map((writing) => ({
            key: `w-${writing.id}`,
            title: writing.title_fr,
            meta:
              writing.status === 'ready'
                ? 'Écrit par Leeral · PDF'
                : writing.status === 'collecting'
                  ? `À terminer · question ${Math.min(writing.current_step + 1, writing.total_steps)} sur ${writing.total_steps}`
                  : writing.status === 'generating'
                    ? 'Leeral écrit…'
                    : 'Pas terminé',
            metaColor: colors.muted,
            category: 'admin' as CategoryCode,
            createdAt: new Date(writing.created_at).getTime(),
            href: (writing.status === 'ready' ? `/ecrit-pret/${writing.id}` : `/ecrit/${writing.id}`) as Href,
          })),
        ].sort((a, b) => b.createdAt - a.createdAt);
        if (alive) setItems(merged);
      })();
      return () => {
        alive = false;
      };
    }, [isGuest]),
  );

  const search = async () => {
    if (recorder.recording) {
      const audio = await recorder.stop();
      if (!audio) return;
      setSearching(true);
      try {
        const heard = await api.transcribe(audio);
        setQuery(heard.text_fr || heard.text);
      } catch (error) {
        await sayError(error);
      } finally {
        setSearching(false);
      }
      return;
    }
    if (await recorder.start()) sayText('Dis ce que tu cherches, puis touche encore le micro.');
    else sayText('Autorise le micro pour chercher à la voix.');
  };

  const visible = useMemo(() => {
    if (!items) return [];
    const words = query
      ? normalize(query)
          .split(/[^a-z0-9]+/)
          .filter((word) => word.length > 3)
      : [];
    return items.filter((item) => {
      if (filter !== 'all' && item.category !== filter) return false;
      if (!words.length) return true;
      const haystack = normalize(`${item.title} ${categoryStyle[item.category].label}`);
      return words.some((word) => haystack.includes(word));
    });
  }, [items, filter, query]);

  const groups = useMemo(() => {
    const map = new Map<string, Item[]>();
    for (const item of visible) {
      const label = groupLabel(item.createdAt);
      map.set(label, [...(map.get(label) ?? []), item]);
    }
    return [...map.entries()];
  }, [visible]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.sand }}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top, paddingHorizontal: 20, paddingBottom: 24, gap: 14 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={{ flex: 1 }}>
            <T display w={700} size={30} lh={1.05} ls={-0.8}>
              Mes documents
            </T>
            <T size={14} color={colors.muted} style={{ marginTop: 4 }}>
              {isGuest
                ? 'Sans compte, ils sont effacés après 24 h'
                : items
                  ? `${plural(items.length, 'document')} gardé${items.length > 1 ? 's' : ''}`
                  : ' '}
            </T>
          </View>
          <Tap
            accessibilityRole="button"
            accessibilityLabel={recorder.recording ? 'Arrêter et chercher' : 'Chercher un document à la voix'}
            onPress={search}
            disabled={searching}
            style={{
              width: 52,
              height: 52,
              borderRadius: 26,
              backgroundColor: recorder.recording ? colors.clay : colors.night,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {searching ? (
              <ActivityIndicator color={colors.light} />
            ) : (
              <Icon
                name={recorder.recording ? 'send' : 'mic'}
                size={22}
                color={recorder.recording ? colors.white : colors.light}
              />
            )}
          </Tap>
          <ScreenSpeaker prompt="app.documents.screen" />
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginHorizontal: -20 }}
          contentContainerStyle={{ paddingHorizontal: 20, gap: 8 }}
        >
          {FILTERS.map((item) => {
            const active = item.id === filter;
            return (
              <Tap
                key={item.id}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                onPress={() => {
                  setFilter(item.id);
                  say(item.prompt);
                }}
                style={{
                  height: 44,
                  paddingHorizontal: 14,
                  borderRadius: 22,
                  backgroundColor: active ? colors.night : colors.paper,
                  borderWidth: 1,
                  borderColor: active ? colors.night : colors.line,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 7,
                }}
              >
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: item.dot }} />
                <T w={700} size={14} color={active ? colors.sand : colors.night}>
                  {item.label}
                </T>
              </Tap>
            );
          })}
        </ScrollView>

        {query ? (
          <Tap
            accessibilityRole="button"
            accessibilityLabel="Effacer la recherche"
            onPress={() => setQuery(null)}
            style={{
              alignSelf: 'flex-start',
              height: 36,
              paddingHorizontal: 12,
              borderRadius: 18,
              backgroundColor: colors.lightSoft,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <T w={600} size={13.5} color={colors.brown} numberOfLines={1} style={{ maxWidth: 260 }}>
              « {query} »
            </T>
            <Icon name="close" size={14} color={colors.brown} />
          </Tap>
        ) : null}

        {!items ? (
          <ActivityIndicator color={colors.night} style={{ marginTop: 40 }} />
        ) : groups.length === 0 ? (
          <View style={{ backgroundColor: colors.paper, borderRadius: 18, padding: 16, gap: 6 }}>
            <T w={700} size={16}>
              {query || filter !== 'all' ? 'Rien trouvé ici.' : 'Aucun document pour l’instant.'}
            </T>
            <T size={14} color={colors.muted}>
              Prends un document en photo depuis l’accueil : il apparaîtra ici.
            </T>
          </View>
        ) : (
          groups.map(([label, list]) => (
            <View key={label} style={{ gap: 8 }}>
              <T w={700} size={12} ls={1.4} upper color={colors.label}>
                {label}
              </T>
              {list.map((item) => {
                const category = categoryStyle[item.category];
                return (
                  <Tap
                    key={item.key}
                    accessibilityRole="button"
                    onPress={() => router.push(item.href)}
                    style={{
                      backgroundColor: colors.paper,
                      borderRadius: 18,
                      padding: 10,
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <View
                      style={{
                        width: 46,
                        height: 56,
                        borderRadius: 10,
                        backgroundColor: category.tint,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon path={category.icon} size={22} color={category.ink} />
                    </View>
                    <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                      <T w={700} size={16} numberOfLines={1}>
                        {item.title}
                      </T>
                      <T w={600} size={13} color={item.metaColor} numberOfLines={1}>
                        {item.meta}
                      </T>
                    </View>
                    <View
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 22,
                        backgroundColor: colors.night,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon name="play" size={15} color={colors.light} />
                    </View>
                  </Tap>
                );
              })}
            </View>
          ))
        )}
      </ScrollView>
      <BottomNav active="documents" />
      <SayBubble bottom={90 + Math.max(insets.bottom - 24, 0)} />
    </View>
  );
}
