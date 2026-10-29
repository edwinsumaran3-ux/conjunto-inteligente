import type { StateCreator } from "zustand";
import type { GridLayout } from "../../types/camera";

export interface CameraSlice {
  gridLayout: GridLayout;
  setGridLayout: (l: GridLayout) => void;
  selectedChannelId: string | null;
  selectChannel: (id: string | null) => void;
  carouselOrientation: "vertical" | "horizontal";
  setCarouselOrientation: (o: "vertical" | "horizontal") => void;
}

export const createCameraSlice: StateCreator<CameraSlice, [], [], CameraSlice> = (set) => ({
  gridLayout: 9,
  setGridLayout: (l) => set({ gridLayout: l }),
  selectedChannelId: null,
  selectChannel: (id) => set({ selectedChannelId: id }),
  carouselOrientation: "horizontal",
  setCarouselOrientation: (o) => set({ carouselOrientation: o }),
});
