import { router, useLocalSearchParams, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { TextInput, View } from 'react-native';

import { Icon } from '@/components/Icon';
import { MicButton } from '@/components/Mic';
import { T } from '@/components/T';
import {
  MiniSpeaker,
  PrimaryButton,
  SayBubble,
  ScreenSpeaker,
  StepDots,
  Tap,
  useInsets,
  useScreenVoice,
} from '@/components/ui';
import { api } from '@/lib/api';
import { useVoiceRecorder } from '@/lib/recorder';
import { useSession } from '@/lib/session';
import { colors, fonts } from '@/lib/theme';

function cleanName(text: string): string {
  return text
    .replace(/[^\p{L}\p{M}\s'-]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 3)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

export default function FirstNameScreen() {
  const { next } = useLocalSearchParams<{ next?: string }>();
  const insets = useInsets();
  const { me, refreshMe } = useSession();
  const { sayError, sayText } = useScreenVoice();
  const recorder = useVoiceRecorder();
  const [name, setName] = useState(me?.user.first_name ?? '');
  const [typing, setTyping] = useState(false);
  const [listening, setListening] = useState(false);
  const [saving, setSaving] = useState(false);

  const toggleMic = async () => {
    if (recorder.recording) {
      const audio = await recorder.stop();
      if (!audio) return;
      setListening(true);
      try {
        const heard = await api.transcribe(audio);
        setName(cleanName(heard.text) || name);
      } catch (error) {
        await sayError(error);
      } finally {
        setListening(false);
      }
      return;
    }
    if (!(await recorder.start())) sayText('Autorise le micro, ou écris ton prénom au clavier.');
  };

  const confirm = async () => {
    const value = cleanName(name);
    if (!value) return;
    setSaving(true);
    try {
      await api.updateMe({ first_name: value, accept_terms: true });
      await refreshMe();
      router.dismissTo((next || '/accueil') as Href);
    } catch (error) {
      await sayError(error);
    } finally {
      setSaving(false);
    }
  };

  const ready = cleanName(name).length > 0;

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.sand,
        paddingTop: insets.top,
        paddingHorizontal: 20,
        paddingBottom: insets.bottom,
        gap: 18,
      }}
    >
      <StatusBar style="dark" />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <View style={{ width: 44 }} />
        <StepDots total={3} current={3} />
        <ScreenSpeaker prompt="app.name.screen" />
      </View>

      <View>
        <T display w={700} size={30} lh={1.05} ls={-0.8}>
          Comment tu t&apos;appelles ?
        </T>
        <T size={15} lh={1.4} color={colors.muted} style={{ marginTop: 6 }}>
          Dis ton prénom. On te le demande une seule fois.
        </T>
      </View>

      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 18 }}>
        <MicButton
          recording={recorder.recording}
          busy={listening}
          onPress={toggleMic}
          size={168}
          inset={20}
          core={92}
          iconSize={38}
          idleLabel="Appuyer et dire mon prénom"
          recordingLabel="J'ai fini de parler"
        />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: -8 }}>
          <T w={700} size={15}>
            {recorder.recording ? 'Je t’écoute… touche pour finir' : 'Appuie et dis ton prénom'}
          </T>
          <MiniSpeaker prompt="app.name.micro" label="Écouter : dire mon prénom" />
        </View>

        <View
          style={{
            alignSelf: 'stretch',
            backgroundColor: colors.paper,
            borderRadius: 22,
            padding: 16,
            gap: 6,
            alignItems: 'center',
          }}
        >
          <T w={700} size={12} ls={1.4} upper color={colors.label}>
            Leeral a entendu
          </T>
          {typing ? (
            <TextInput
              value={name}
              onChangeText={setName}
              autoFocus
              autoCapitalize="words"
              placeholder="Ton prénom"
              placeholderTextColor={colors.placeholder}
              onSubmitEditing={() => setTyping(false)}
              style={{
                fontFamily: fonts.display800,
                fontSize: 36,
                color: colors.night,
                textAlign: 'center',
                minWidth: 200,
                paddingVertical: 4,
              }}
            />
          ) : (
            <T
              display
              w={800}
              size={40}
              ls={-1}
              color={name ? colors.night : colors.placeholder}
              numberOfLines={1}
              adjustsFontSizeToFit
            >
              {name || '…'}
            </T>
          )}
          <Tap
            accessibilityRole="button"
            onPress={() => setTyping((value) => !value)}
            style={{
              height: 44,
              paddingHorizontal: 14,
              borderRadius: 22,
              backgroundColor: colors.sand,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Icon name="keyboard" size={16} />
            <T w={700} size={14}>
              {typing ? 'Valider' : 'Écrire au clavier'}
            </T>
          </Tap>
        </View>
      </View>

      <View>
        <PrimaryButton
          label="Oui, c'est moi"
          bg={ready ? colors.night : colors.line}
          fg={ready ? colors.sand : colors.label}
          disabled={!ready}
          loading={saving}
          onPress={confirm}
          left={<Icon name="check" size={20} color={ready ? colors.light : colors.label} />}
        />
        <MiniSpeaker
          prompt="app.name.go"
          label="Écouter : valider"
          color={ready ? colors.sand : colors.label}
          style={{ position: 'absolute', right: 6, top: 11 }}
        />
      </View>

      <SayBubble top={insets.top + 64} />
    </View>
  );
}
