/** Electron preload 暴露的 API 类型 */

interface SpeakWiseOverlay {
  show: () => Promise<boolean>;
  hide: () => Promise<boolean>;
  isVisible: () => Promise<boolean>;
  setContent: (text: string) => void;
  setOpacity: (value: number) => void;
  setScrollSpeed: (speed: string) => void;
  setAutoScroll: (enabled: boolean) => void;
}

interface SpeakWiseAPI {
  platform: string;
  backendHost: string;
  backendPort: number;
  overlay: SpeakWiseOverlay;
  openFolder: (dir: string) => void;
}

declare global {
  interface Window {
    speakwise?: SpeakWiseAPI;
  }
}

export {};
