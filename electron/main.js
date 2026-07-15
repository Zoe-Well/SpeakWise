/**
 * Electron 主进程
 * 职责：BrowserWindow 主窗口 + Copilot 悬浮窗 + 后端生命周期
 */

const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

let mainWindow = null;
let overlayWindow = null;
let backendProcess = null;

const BACKEND_PORT = 8001;
const BACKEND_HOST = "127.0.0.1";
// 生产检测: app.isPackaged 或 resourcesPath 下有 bundled backend
const bundledExePath = path.join(process.resourcesPath || "", "backend", "speakwise-backend.exe");
const isDev = !app.isPackaged && !fs.existsSync(bundledExePath);
const FRONTEND_URL = isDev
  ? "http://localhost:5173"
  : `file://${path.join(__dirname, "frontend", "dist", "index.html")}`;

// ── Backend lifecycle ──────────────────────────────────────

function startBackend() {
  const projectDir = path.join(__dirname, "..");
  const userDataDir = app.getPath("userData");
  const dataDir = path.join(userDataDir, "speakwise-data");
  try { fs.mkdirSync(dataDir, { recursive: true }); } catch (e) { /* ignore */ }

  // Find backend
  const exeDir = path.dirname(process.execPath);
  const bundledExe = path.join(exeDir, "resources", "backend", "speakwise-backend.exe");
  const devPython = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
  const devArgs = ["-m", "uvicorn", "backend.src.main:app", "--host", BACKEND_HOST, "--port", String(BACKEND_PORT)];

  let cmd, args, cwd;
  if (fs.existsSync(bundledExe)) {
    cmd = bundledExe; args = ["--host", BACKEND_HOST, "--port", String(BACKEND_PORT)]; cwd = exeDir;
  } else if (!app.isPackaged) {
    cmd = devPython; args = devArgs; cwd = projectDir;
  } else {
    return;
  }

  backendProcess = spawn(cmd, args, {
    cwd, stdio: "pipe",
    env: { ...process.env, SPEAKWISE_DATA_DIR: dataDir },
  });
  backendProcess.stdout.on("data", (data) => process.stdout.write(`[backend] ${data}`));
  backendProcess.stderr.on("data", (data) => process.stderr.write(`[backend] ${data}`));
  backendProcess.on("error", (err) => { process.stderr.write(`[backend] spawn error: ${err}\n`); });
  backendProcess.on("exit", (code) => { process.stderr.write(`[backend] exited with code ${code}\n`); });
}

function stopBackend() {
  if (backendProcess) { backendProcess.kill(); backendProcess = null; }
}

// ── Main window ────────────────────────────────────────────

function createWindow() {
  // Grant persistent microphone access (no repeated prompts)
  const { session: { defaultSession } } = require("electron");
  defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(permission === "media");
  });
  defaultSession.setPermissionCheckHandler((_wc, permission) => {
    return permission === "media";
  });

  mainWindow = new BrowserWindow({
    width: 1200, height: 800, minWidth: 900, minHeight: 600,
    title: "SpeakWise 智能面试助手",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false, contextIsolation: true,
    },
  });
  mainWindow.loadURL(FRONTEND_URL);
  if (process.env.NODE_ENV === "development") mainWindow.webContents.openDevTools();
  mainWindow.on("closed", () => { mainWindow = null; });
}

// ── Copilot overlay window ─────────────────────────────────

const DEFAULT_OVERLAY_SETTINGS = { x: 50, y: 50, width: 600, height: 300, opacity: 0.90, scrollSpeed: 1.0, fontSize: 18, autoScroll: true };

function getOverlaySettingsPath() { return path.join(app.getPath("userData"), "overlay-settings.json"); }
function loadOverlaySettings() {
  try { const p = getOverlaySettingsPath(); if (fs.existsSync(p)) { return { ...DEFAULT_OVERLAY_SETTINGS, ...JSON.parse(fs.readFileSync(p, "utf-8")) }; } } catch (e) {}
  return { ...DEFAULT_OVERLAY_SETTINGS };
}
function saveOverlaySettings(s) { try { fs.writeFileSync(getOverlaySettingsPath(), JSON.stringify(s, null, 2), "utf-8"); } catch (e) {} }

function createOverlay() {
  if (overlayWindow) return;
  const s = loadOverlaySettings();

  overlayWindow = new BrowserWindow({
    width: s.width, height: s.height,
    x: s.x, y: s.y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: true,
    hasShadow: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, "overlay-preload.js"),
      nodeIntegration: false, contextIsolation: true,
    },
  });

  overlayWindow.loadFile(path.join(__dirname, "overlay.html"));
  overlayWindow.setAlwaysOnTop(true, "screen-saver");
  overlayWindow.setVisibleOnAllWorkspaces(true);
  overlayWindow.setOpacity(s.opacity);
  overlayWindow.on("resize", () => { const [w, h] = overlayWindow.getSize(); s.width = w; s.height = h; saveOverlaySettings(s); });
  overlayWindow.on("moved", () => { const [x, y] = overlayWindow.getPosition(); s.x = x; s.y = y; saveOverlaySettings(s); });

  overlayWindow.on("closed", () => { overlayWindow = null; });
}

function destroyOverlay() {
  if (overlayWindow) { overlayWindow.close(); overlayWindow = null; }
}

// ── IPC handlers ───────────────────────────────────────────

function setupIPC() {
  // Overlay lifecycle
  ipcMain.handle("open-folder", (_e, dir) => { shell.openPath(dir); });
  ipcMain.handle("overlay:load-settings", () => loadOverlaySettings());
  ipcMain.on("overlay:save-settings", (_e, settings) => { saveOverlaySettings({ ...loadOverlaySettings(), ...settings }); });
  ipcMain.handle("overlay:show", () => { createOverlay(); return true; });
  ipcMain.handle("overlay:hide", () => { destroyOverlay(); return true; });
  ipcMain.handle("overlay:is-visible", () => !!overlayWindow);

  // Content update (from main window renderer to overlay)
  ipcMain.on("overlay:set-content", (_event, text) => {
    if (overlayWindow) overlayWindow.webContents.send("overlay:content", text);
  });

  // Settings update
  ipcMain.on("overlay:set-opacity", (_event, value) => {
    if (overlayWindow) {
      const v = Math.max(0.35, Math.min(1.0, value));
      overlayWindow.setOpacity(v);
      overlayWindow.webContents.send("overlay:opacity", v);
    }
  });

  ipcMain.on("overlay:set-scroll", (_event, speed) => {
    if (overlayWindow) overlayWindow.webContents.send("overlay:scroll-speed", speed);
  });

  ipcMain.on("overlay:set-auto-scroll", (_event, enabled) => {
    if (overlayWindow) overlayWindow.webContents.send("overlay:auto-scroll", enabled);
  });

  // Forward backend port info
  ipcMain.on("overlay:move-by", (_e, dx, dy) => {
    if (overlayWindow) {
      const [x, y] = overlayWindow.getPosition();
      overlayWindow.setPosition(x + Math.round(dx), y + Math.round(dy));
    }
  });
  ipcMain.handle("get-backend-info", () => ({
    host: BACKEND_HOST, port: BACKEND_PORT,
  }));
}

// ── App lifecycle ──────────────────────────────────────────

async function waitForBackend(timeoutMs = 20000) {
  const http = require("http");
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/health`, (res) => {
          res.resume(); resolve(true);
        });
        req.on("error", reject);
        req.setTimeout(2000, () => { req.destroy(); reject(new Error("timeout")); });
      });
      return true;
    } catch (e) {
      await new Promise(r => setTimeout(r, 800));
    }
  }
  return false;
}

app.whenReady().then(async () => {
  startBackend();
  setupIPC();

  // Wait for backend health
  const healthy = await waitForBackend();
  if (!healthy) {
    const { dialog } = require("electron");
    dialog.showErrorBox("启动失败", `无法连接后端 (http://${BACKEND_HOST}:${BACKEND_PORT})\n\n请检查端口是否被占用，或尝试重启。`);
    app.quit();
    return;
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  destroyOverlay();
  stopBackend();
});
