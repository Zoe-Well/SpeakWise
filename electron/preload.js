/**
 * Electron Preload — 主窗口渲染进程 API
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("speakwise", {
  platform: process.platform,
  backendHost: "127.0.0.1",
  backendPort: 8001,

  // ── Utilities ──
  openFolder: (dir) => ipcRenderer.invoke("open-folder", dir),

  // ── Copilot overlay ──
  overlay: {
    show: () => ipcRenderer.invoke("overlay:show"),
    hide: () => ipcRenderer.invoke("overlay:hide"),
    isVisible: () => ipcRenderer.invoke("overlay:is-visible"),
    setContent: (text) => ipcRenderer.send("overlay:set-content", text),
    setOpacity: (value) => ipcRenderer.send("overlay:set-opacity", value),
    setScrollSpeed: (speed) => ipcRenderer.send("overlay:set-scroll", speed),
    setAutoScroll: (enabled) => ipcRenderer.send("overlay:set-auto-scroll", enabled),
  },
});
