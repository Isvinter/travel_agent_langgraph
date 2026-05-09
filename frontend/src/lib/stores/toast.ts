import { writable } from "svelte/store";

export interface ToastMessage {
  id: number;
  message: string;
  link?: string;
  linkText?: string;
  duration?: number;
}

export const toastMessages = writable<ToastMessage[]>([]);

let nextId = 0;

export function showToast(
  message: string,
  link?: string,
  linkText?: string,
  duration: number = 8000,
): number {
  const id = nextId++;
  toastMessages.update((msgs) => [...msgs, { id, message, link, linkText, duration }]);

  if (duration > 0) {
    setTimeout(() => {
      toastMessages.update((msgs) => msgs.filter((m) => m.id !== id));
    }, duration);
  }

  return id;
}

export function dismissToast(id: number) {
  toastMessages.update((msgs) => msgs.filter((m) => m.id !== id));
}
