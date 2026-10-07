import { useState } from 'react';
import { ActivityIndicator, TextInput, View } from 'react-native';

import { LANGUAGE_NAMES } from '@/lib/format';
import { colors, fonts } from '@/lib/theme';
import type { Language, TextLanguage } from '@/lib/types';

import { Icon } from './Icon';
import { T } from './T';
import { Tap } from './ui';

type Props = {
  language: Language;
  placeholder: string;
  busy?: boolean;
  onSend: (text: string, language: TextLanguage) => void;
  onClose: () => void;
};

export function TextAnswer({ language, placeholder, busy = false, onSend, onClose }: Props) {
  const [text, setText] = useState('');
  const [written, setWritten] = useState<TextLanguage>('fr');
  const send = () => {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value, written);
    setText('');
  };
  return (
    <View style={{ alignSelf: 'stretch', gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
        <T w={600} size={13} color={colors.muted} style={{ flex: 1 }}>
          J&apos;écris en :
        </T>
        {(['fr', language] as TextLanguage[]).map((code) => {
          const active = code === written;
          return (
            <Tap
              key={code}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => setWritten(code)}
              style={{
                height: 32,
                paddingHorizontal: 12,
                borderRadius: 16,
                backgroundColor: active ? colors.night : colors.sand,
                justifyContent: 'center',
              }}
            >
              <T w={700} size={13} color={active ? colors.sand : colors.night}>
                {code === 'fr' ? 'Français' : LANGUAGE_NAMES[code as Language]}
              </T>
            </Tap>
          );
        })}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Tap
          accessibilityRole="button"
          accessibilityLabel="Revenir au micro"
          onPress={onClose}
          style={{
            width: 48,
            height: 48,
            borderRadius: 24,
            backgroundColor: colors.sand,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="mic" size={20} />
        </Tap>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder={placeholder}
          placeholderTextColor={colors.placeholder}
          autoFocus
          multiline
          onSubmitEditing={send}
          style={{
            flex: 1,
            minHeight: 48,
            maxHeight: 120,
            borderRadius: 18,
            backgroundColor: colors.sand,
            paddingHorizontal: 14,
            paddingVertical: 12,
            fontFamily: fonts.body600,
            fontSize: 16,
            color: colors.night,
          }}
        />
        <Tap
          accessibilityRole="button"
          accessibilityLabel="Envoyer"
          onPress={send}
          disabled={busy || !text.trim()}
          style={{
            width: 48,
            height: 48,
            borderRadius: 24,
            backgroundColor: text.trim() ? colors.light : colors.line,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {busy ? (
            <ActivityIndicator color={colors.night} />
          ) : (
            <Icon name="send" size={20} color={colors.night} />
          )}
        </Tap>
      </View>
    </View>
  );
}
