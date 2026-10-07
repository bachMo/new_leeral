import type { LocalFile } from './types';

let pending: LocalFile[] = [];

export const capture = {
  set(files: LocalFile[]): void {
    pending = files;
  },
  take(): LocalFile[] {
    const files = pending;
    pending = [];
    return files;
  },
  peek(): LocalFile[] {
    return pending;
  },
};
