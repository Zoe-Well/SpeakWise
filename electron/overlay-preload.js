/**
 * Electron Preload — 悬浮窗渲染进程 API
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("overlayAPI", {
  onContent: (callback) => {
    ipcRenderer.on("overlay:content", (_event, text) => callback(text));
  },
  onOpacity: (callback) => {
    ipcRenderer.on("overlay:opacity", (_event, value) => callback(value));
  },
  onScrollSpeed: (callback) => {
    ipcRenderer.on("overlay:scroll-speed", (_event, speed) => callback(speed));
  },
  onAutoScroll: (callback) => {
    ipcRenderer.on("overlay:auto-scroll", (_event, enabled) => callback(enabled));
  },
  moveBy: (dx, dy) => {
    ipcRenderer.send("overlay:move-by", dx, dy);
  },
  setOpacity: (value) => {
    ipcRenderer.send("overlay:set-opacity", value);
  },
  closeOverlay: () => {
    ipcRenderer.send("overlay:close");
  },
  loadSettings: () => ipcRenderer.invoke("overlay:load-settings"),
  saveSettings: (settings) => ipcRenderer.send("overlay:save-settings", settings),
});
