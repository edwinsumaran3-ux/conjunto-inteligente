import { create } from "zustand";
import { createUiSlice, type UiSlice } from "./slices/uiSlice";
import { createCameraSlice, type CameraSlice } from "./slices/cameraSlice";

// El store compone slices independientes (una responsabilidad por slice,
// en su propio archivo bajo store/slices/) en lugar de acumular todo el
// estado global en un único módulo. Añadir un dominio nuevo de estado
// significa crear un slice nuevo, nunca ampliar uno existente con algo
// que no le corresponde.
export type AppState = UiSlice & CameraSlice;

export const useStore = create<AppState>()((...a) => ({
  ...createUiSlice(...a),
  ...createCameraSlice(...a),
}));
