import { useEffect, useState } from "react";

export type ActivityPanelPreferences = {
  showCommands: boolean;
  showCommandOutput: boolean;
  showFileChanges: boolean;
};

const STORAGE_KEY = "navi-activity-panel-preferences";
const DEFAULT_PREFERENCES: ActivityPanelPreferences = {
  showCommands: true,
  showCommandOutput: false,
  showFileChanges: true,
};

type Listener = () => void;
const listeners = new Set<Listener>();

const readPreferences = (): ActivityPanelPreferences => {
  if (typeof window === "undefined") {
    return { ...DEFAULT_PREFERENCES };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    const parsed = JSON.parse(raw) as Partial<ActivityPanelPreferences>;
    return {
      showCommands: parsed.showCommands ?? DEFAULT_PREFERENCES.showCommands,
      showCommandOutput: parsed.showCommandOutput ?? DEFAULT_PREFERENCES.showCommandOutput,
      showFileChanges: parsed.showFileChanges ?? DEFAULT_PREFERENCES.showFileChanges,
    };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
};

let currentPreferences = readPreferences();

export const updateActivityPanelPreferences = (next: Partial<ActivityPanelPreferences>) => {
  currentPreferences = { ...currentPreferences, ...next };
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(currentPreferences));
    } catch {
      // ignore storage failures
    }
  }
  listeners.forEach((listener) => listener());
};

export const useActivityPanelPreferences = (): [
  ActivityPanelPreferences,
  (next: Partial<ActivityPanelPreferences>) => void
] => {
  const [preferences, setPreferences] = useState<ActivityPanelPreferences>(() => currentPreferences);

  useEffect(() => {
    const handleUpdate = () => setPreferences(currentPreferences);
    listeners.add(handleUpdate);
    return () => {
      listeners.delete(handleUpdate);
    };
  }, []);

  return [preferences, updateActivityPanelPreferences];
};
