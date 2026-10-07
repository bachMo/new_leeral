import { CameraView, useCameraPermissions } from 'expo-camera';
import { router, useIsFocused } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Linking, StyleSheet, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { T } from '@/components/T';
import {
  BackButton,
  MiniSpeaker,
  SayBubble,
  ScreenSpeaker,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { capture } from '@/lib/capture';
import { MAX_PAGES } from '@/lib/config';
import { prepareImage } from '@/lib/pickers';
import { colors } from '@/lib/theme';
import type { LocalFile } from '@/lib/types';

const CORNER = 34;

function Corners({ color }: { color: string }) {
  const base = { position: 'absolute' as const, width: CORNER, height: CORNER, borderColor: color };
  return (
    <>
      <View
        style={[base, { left: 44, top: 70, borderLeftWidth: 4, borderTopWidth: 4, borderTopLeftRadius: 10 }]}
      />
      <View
        style={[
          base,
          { right: 44, top: 70, borderRightWidth: 4, borderTopWidth: 4, borderTopRightRadius: 10 },
        ]}
      />
      <View
        style={[
          base,
          { left: 44, bottom: 70, borderLeftWidth: 4, borderBottomWidth: 4, borderBottomLeftRadius: 10 },
        ]}
      />
      <View
        style={[
          base,
          { right: 44, bottom: 70, borderRightWidth: 4, borderBottomWidth: 4, borderBottomRightRadius: 10 },
        ]}
      />
    </>
  );
}

export default function CameraScreen() {
  const insets = useInsets();
  const focused = useIsFocused();
  const { say, sayError } = useScreenVoice();
  const [permission, requestPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [pages, setPages] = useState<LocalFile[]>([]);
  const [shooting, setShooting] = useState(false);
  const [ready, setReady] = useState(false);
  const count = pages.length;

  useEffect(() => {
    if (!focused) setReady(false);
  }, [focused]);
  const guide = count === 0 ? colors.light : colors.riverGlow;
  const tip =
    count === 0
      ? 'Pose le document à plat, dans un endroit éclairé.'
      : `Page ${count} prise. Une autre page ? Prends-la aussi.`;

  const shoot = async () => {
    if (!camera.current || !ready || shooting || count >= MAX_PAGES) return;
    setShooting(true);
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.85 });
      if (photo?.uri) {
        const page = await prepareImage(photo.uri, photo.width, photo.height, count);
        setPages((current) => [...current, page]);
      }
    } catch (error) {
      await sayError(error);
    } finally {
      setShooting(false);
    }
  };

  const finish = () => {
    capture.set(pages);
    router.replace('/lecture');
  };

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.nightDeep,
        paddingTop: insets.top,
        paddingHorizontal: 20,
        paddingBottom: insets.bottom,
        gap: 14,
      }}
    >
      <StatusBar style="light" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <BackButton dark close label="Annuler" />
        <T display w={700} size={20} color={colors.sand} center style={{ flex: 1 }}>
          {count === 0 ? 'Prends la photo' : `Page ${count + 1}`}
        </T>
        <ScreenSpeaker prompt="app.camera.screen" dark />
      </View>

      <View
        style={{
          flex: 1,
          borderRadius: 28,
          backgroundColor: colors.nightBox,
          overflow: 'hidden',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {permission?.granted && focused ? (
          <CameraView
            ref={camera}
            style={StyleSheet.absoluteFill}
            facing="back"
            onCameraReady={() => setReady(true)}
          />
        ) : permission && !permission.granted ? (
          <View style={{ alignItems: 'center', gap: 14, paddingHorizontal: 28 }}>
            <T size={16} lh={1.45} color={colors.sand} center>
              Leeral a besoin de la caméra pour photographier ton document.
            </T>
            <Tap
              accessibilityRole="button"
              onPress={() => (permission.canAskAgain ? requestPermission() : Linking.openSettings())}
              style={{
                height: 52,
                paddingHorizontal: 20,
                borderRadius: 26,
                backgroundColor: colors.light,
                justifyContent: 'center',
              }}
            >
              <T display w={700} size={17}>
                Autoriser la caméra
              </T>
            </Tap>
          </View>
        ) : (
          <ActivityIndicator color={colors.light} />
        )}
        <Corners color={guide} />
        <View
          style={{
            position: 'absolute',
            left: 14,
            right: 14,
            top: 14,
            backgroundColor: 'rgba(11,22,38,0.82)',
            borderRadius: 18,
            paddingVertical: 6,
            paddingLeft: 14,
            paddingRight: 4,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: guide }} />
          <T w={600} size={14.5} lh={1.3} color={colors.sand} style={{ flex: 1 }}>
            {tip}
          </T>
          <MiniSpeaker
            label="Écouter le conseil"
            color={colors.sand}
            width={40}
            height={40}
            opacity={0.6}
            onPress={() => say(count === 0 ? 'app.camera.tip_first' : 'app.camera.tip_next')}
          />
        </View>
      </View>

      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {pages.slice(-4).map((page, index) => {
            const number = Math.max(count - 4, 0) + index + 1;
            return (
              <View
                key={page.uri}
                style={{
                  width: 34,
                  height: 46,
                  borderRadius: 6,
                  backgroundColor: '#EFE8D8',
                  borderWidth: 2,
                  borderColor: colors.light,
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  paddingBottom: 3,
                }}
              >
                <T display w={800} size={12}>
                  {number}
                </T>
              </View>
            );
          })}
        </View>
        <Tap
          accessibilityRole="button"
          accessibilityLabel="Prendre la photo"
          onPress={shoot}
          disabled={!permission?.granted || !ready || shooting}
        >
          <View style={{ width: 112, height: 112, alignItems: 'center', justifyContent: 'center' }}>
            <View
              style={[
                StyleSheet.absoluteFill,
                { borderRadius: 56, backgroundColor: colors.light, opacity: 0.14 },
              ]}
            />
            <View
              style={{
                position: 'absolute',
                top: 13,
                left: 13,
                right: 13,
                bottom: 13,
                borderRadius: 43,
                backgroundColor: colors.light,
                opacity: 0.26,
              }}
            />
            <View
              style={{
                width: 74,
                height: 74,
                borderRadius: 37,
                backgroundColor: colors.light,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <View
                style={{
                  width: 68,
                  height: 68,
                  borderRadius: 34,
                  borderWidth: 4,
                  borderColor: colors.nightDeep,
                  backgroundColor: colors.light,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {shooting ? <ActivityIndicator color={colors.night} /> : null}
              </View>
            </View>
          </View>
        </Tap>
        <View style={{ flex: 1, alignItems: 'flex-end' }}>
          {count > 0 ? (
            <Tap
              accessibilityRole="button"
              onPress={finish}
              style={{
                height: 52,
                paddingHorizontal: 16,
                borderRadius: 26,
                backgroundColor: colors.sand,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Icon name="check" size={18} color={colors.night} />
              <T w={800} size={15}>
                Terminé
              </T>
            </Tap>
          ) : null}
        </View>
      </View>
      <T size={14} color={colors.onNightMuted} center style={{ minHeight: 20 }}>
        {count === 0
          ? 'Touche le grand bouton'
          : `${count} ${count > 1 ? 'pages' : 'page'} · touche Terminé quand c’est fini`}
      </T>

      <SayBubble light top={insets.top + 64} />
    </View>
  );
}
