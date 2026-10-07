import * as DocumentPicker from 'expo-document-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { Platform } from 'react-native';

import { MAX_PAGES } from './config';
import type { LocalFile } from './types';

const MAX_SIDE = 2000;

const DOCUMENT_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

export async function prepareImage(
  uri: string,
  width: number,
  height: number,
  index: number,
): Promise<LocalFile> {
  const name = `page-${index + 1}.jpg`;
  try {
    const context = ImageManipulator.manipulate(uri);
    const longest = Math.max(width, height);
    if (longest > MAX_SIDE) {
      context.resize(width >= height ? { width: MAX_SIDE } : { height: MAX_SIDE });
    }
    const rendered = await context.renderAsync();
    const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.85 });
    return { uri: saved.uri, name, type: 'image/jpeg' };
  } catch {
    return { uri, name, type: 'image/jpeg' };
  }
}

export async function pickPhotos(): Promise<LocalFile[] | null> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted && Platform.OS !== 'web') return null;
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsMultipleSelection: true,
    selectionLimit: MAX_PAGES,
    quality: 0.9,
  });
  if (result.canceled || !result.assets.length) return null;
  const pages: LocalFile[] = [];
  for (const [index, asset] of result.assets.slice(0, MAX_PAGES).entries()) {
    pages.push(await prepareImage(asset.uri, asset.width, asset.height, index));
  }
  return pages;
}

export async function pickDocument(): Promise<LocalFile[] | null> {
  const result = await DocumentPicker.getDocumentAsync({
    type: DOCUMENT_TYPES,
    multiple: false,
    copyToCacheDirectory: true,
  });
  if (result.canceled || !result.assets.length) return null;
  const asset = result.assets[0];
  const isPdf = asset.name.toLowerCase().endsWith('.pdf') || asset.mimeType === 'application/pdf';
  return [
    {
      uri: asset.uri,
      name: asset.name || (isPdf ? 'document.pdf' : 'document.docx'),
      type: asset.mimeType ?? (isPdf ? DOCUMENT_TYPES[0] : DOCUMENT_TYPES[1]),
    },
  ];
}
