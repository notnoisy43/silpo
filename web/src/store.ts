import { create } from "zustand";

type ApiStatus = "unknown" | "ok" | "down";

interface AppState {
  apiStatus: ApiStatus;
  setApiStatus: (status: ApiStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  apiStatus: "unknown",
  setApiStatus: (apiStatus) => set({ apiStatus }),
}));
