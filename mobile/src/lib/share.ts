import { Directory, File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as WebBrowser from 'expo-web-browser';
import { Linking, Platform } from 'react-native';

export async function sharePdf(url: string, filename: string): Promise<void> {
  if (Platform.OS === 'web' || !(await Sharing.isAvailableAsync())) {
    await WebBrowser.openBrowserAsync(url);
    return;
  }
  const folder = new Directory(Paths.cache, 'leeral');
  if (!folder.exists) folder.create();
  const target = new File(folder, filename);
  if (target.exists) target.delete();
  const downloaded = await File.downloadFileAsync(url, target);
  await Sharing.shareAsync(downloaded.uri, {
    mimeType: 'application/pdf',
    dialogTitle: filename,
    UTI: 'com.adobe.pdf',
  });
}

export async function openPdf(url: string): Promise<void> {
  if (Platform.OS === 'android') {
    await Linking.openURL(url);
    return;
  }
  await WebBrowser.openBrowserAsync(url);
}
