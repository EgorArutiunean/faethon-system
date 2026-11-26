import { useLayoutEffect, useRef, useState } from "react";

import { useAuth } from "../auth";

type Options<T> = {
  scope: string;
  entityId: string | number;
  revision: string;
  value: T;
  dirty: boolean;
  enabled: boolean;
  validate: (value: unknown) => boolean;
  onRestore: (value: T) => void;
  onDiscard: () => void;
};

export type LocalDraftStatus = {
  recoveredAt: string | null;
  stale: boolean;
  storageError: boolean;
  clear: () => void;
  discard: () => void;
};

export function useLocalDraft<T>(options: Options<T>): LocalDraftStatus {
  const { user } = useAuth();
  const key = `buy-modern-input:${user?.id}:${options.scope}:${options.entityId}`;
  const enabled = options.enabled && Boolean(user?.id);
  const [recoveredAt, setRecoveredAt] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const active = useRef<{ key: string; revision: string; blocked: boolean } | null>(null);
  const callbacks = useRef(options);
  callbacks.current = options;
  const serialized = JSON.stringify(options.value);

  useLayoutEffect(() => {
    if (!enabled) {
      active.current = null;
      setRecoveredAt(null);
      setStale(false);
      return;
    }
    if (active.current?.key !== key || active.current.revision !== options.revision) {
      active.current = { key, revision: options.revision, blocked: false };
      setRecoveredAt(null);
      setStale(false);
      setStorageError(false);
      try {
        const raw = localStorage.getItem(key);
        if (!raw) {
          if (options.dirty) localStorage.setItem(key, JSON.stringify({ version: 1, revision: options.revision, value: options.value, savedAt: new Date().toISOString() }));
          return;
        }
        const saved: unknown = JSON.parse(raw);
        if (!saved || typeof saved !== "object" || !("version" in saved) || saved.version !== 1
          || !("revision" in saved) || typeof saved.revision !== "string" || !("value" in saved)
          || !("savedAt" in saved) || typeof saved.savedAt !== "string") {
          localStorage.removeItem(key);
          return;
        }
        if (saved.revision !== options.revision) {
          active.current.blocked = true;
          setStale(true);
          return;
        }
        if (!callbacks.current.validate(saved.value)) {
          localStorage.removeItem(key);
          return;
        }
        setRecoveredAt(saved.savedAt);
        callbacks.current.onRestore(saved.value as T);
      } catch {
        setStorageError(true);
      }
      // Wait for the parent to apply the restored fields before writing this key.
      return;
    }
    if (active.current.blocked) return;
    try {
      if (options.dirty) {
        localStorage.setItem(key, JSON.stringify({ version: 1, revision: options.revision, value: options.value, savedAt: new Date().toISOString() }));
      } else {
        localStorage.removeItem(key);
        setRecoveredAt(null);
      }
    } catch {
      setStorageError(true);
    }
  }, [key, enabled, options.revision, serialized, options.dirty, stale]);

  function clear() {
    try { localStorage.removeItem(key); } catch { setStorageError(true); }
    // A completed request may belong to an editor the user has already left.
    if (active.current?.key !== key || active.current.revision !== options.revision) return;
    active.current = { key, revision: options.revision, blocked: false };
    setRecoveredAt(null);
    setStale(false);
  }

  function discard() {
    const wasStale = active.current?.blocked;
    clear();
    if (!wasStale) callbacks.current.onDiscard();
  }

  return { recoveredAt, stale, storageError, clear, discard };
}
