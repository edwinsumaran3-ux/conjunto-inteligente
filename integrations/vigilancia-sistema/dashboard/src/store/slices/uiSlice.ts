import type { StateCreator } from "zustand";

export interface UiSlice {
  mode: "FULL" | "PARTIAL" | "LOCAL" | "SAFE";
  setMode: (m: UiSlice["mode"]) => void;
  dark: boolean;
  toggleDark: () => void;
  pinned: Set<string>;
  togglePin: (id: string) => void;
}

export const createUiSlice: StateCreator<UiSlice, [], [], UiSlice> = (set) => ({
  mode: "FULL",
  setMode: (m) => set({ mode: m }),
  dark: true,
  toggleDark: () => set((s) => ({ dark: !s.dark })),
  pinned: new Set(),
  togglePin: (id) =>
    set((s) => {
      const next = new Set(s.pinned);
      next.has(id) ? next.delete(id) : next.add(id);
      return { pinned: next };
    }),
});
