/**
 * Conversation state, kept outside React.
 *
 * `App.jsx` switches pages by swapping the lazy component, which unmounts the
 * old one — so anything the Agent tab held in `useState` was lost the moment the
 * user looked at their holdings and came back. Follow-ups like "why that one?"
 * are the whole point of a chat tab, so the history has to outlive the mount.
 *
 * A module-level store read through `useSyncExternalStore` survives unmounting
 * without prop-drilling through `App.jsx`, and without a `setState` inside an
 * effect (which the lint config treats as an error).
 *
 * Deliberately not persisted: a reload starts fresh. Decisions worth keeping go
 * to the advisor's journal on the backend, which records the numbers too.
 */
import { useSyncExternalStore } from "react";

const listeners = new Set();

let snapshot = { messages: [], pending: false };

function emit(next) {
  snapshot = { ...snapshot, ...next };
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return snapshot;
}

/** Live view of the conversation. Re-renders on every change. */
export function useChat() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function appendMessage(message) {
  emit({ messages: [...snapshot.messages, message] });
}

export function setPending(pending) {
  emit({ pending });
}

export function clearChat() {
  emit({ messages: [], pending: false });
}

/** The [{role, content}] shape the backend expects — no UI-only fields. */
export function toHistory(messages) {
  return messages.map(({ role, content }) => ({ role, content }));
}
