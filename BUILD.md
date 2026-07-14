# SpeakWise 打包发布教程

## 概览

打包流程：

```
前端 build         后端 PyInstaller       Electron-builder
─────────         ─────────────────       ─────────────────
npm run build  →  pyinstaller  →  .exe  →  nsis installer  →  SpeakWise Setup.exe
(生成 dist/)      (生成单个 exe)           (Windows 安装包)
```

---

## 前置要求

打包前确保已安装：

```powershell
# Node.js 依赖
cd electron && npm install

# Python 依赖（PyInstaller）
uv pip install pyinstaller
```

---

## 步骤 1：构建前端

```powershell
cd frontend
npm run build
```

成功后在 `frontend/dist/` 生成：
- `index.html`
- `assets/index-*.js`
- `assets/index-*.css`

---

## 步骤 2：打包 Python 后端为独立 exe

```powershell
cd c:\AgentProjects\SpeakWise

pyinstaller `
  --onefile `
  --name speakwise-backend `
  --add-data "backend/src/prompts;prompts" `
  --hidden-import=sse_starlette `
  --hidden-import=sqlmodel `
  --hidden-import=pypdf `
  --hidden-import=docx `
  --hidden-import=dotenv `
  --collect-all openai `
  backend/src/main.py
```

成功后在 `dist/` 生成 `speakwise-backend.exe`。

> **验证**：运行 `.\dist\speakwise-backend.exe --port 8001`，访问 `http://127.0.0.1:8001/api/health` 确认返回 `{"status":"ok"}`。

---

## 步骤 3：确保文件结构正确

打包前确认以下文件存在：

```
electron/
├── main.js
├── preload.js
├── overlay.html
├── overlay-preload.js
└── package.json

frontend/
└── dist/
    ├── index.html
    └── assets/

dist/
└── speakwise-backend.exe    ← 步骤 2 生成
```

---

## 步骤 4：配置 electron-builder

`electron/package.json` 已包含 `build` 字段：

```json
{
  "build": {
    "appId": "com.speakwise.app",
    "productName": "SpeakWise",
    "directories": {
      "output": "../dist",
      "buildResources": "../frontend/dist"
    },
    "files": [
      "main.js",
      "preload.js",
      "overlay.html",
      "overlay-preload.js",
      "../frontend/dist/**/*"
    ],
    "extraResources": [
      {
        "from": "../dist/speakwise-backend",
        "to": "backend"
      }
    ],
    "win": {
      "target": "nsis"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "createDesktopShortcut": true,
      "shortcutName": "SpeakWise"
    }
  }
}
```

---

## 步骤 5：打包

```powershell
cd electron
npm run build
```

打包完成后在项目根目录 `dist/` 生成：
- `SpeakWise Setup x.x.x.exe` — 用户安装包
- `SpeakWise-x.x.x-win.zip` — 便携版

---

## 步骤 6：测试安装包

1. 复制 `SpeakWise Setup x.x.x.exe` 到另一台电脑
2. 安装 → 启动 → 确认：
   - ✅ 应用正常打开
   - ✅ 进入设置页，输入 DeepSeek API Key
   - ✅ 创建会话，发送 `/intro`，得到回复
   - ✅ 提词器悬浮窗可打开/拖拽
   - ✅ 数据存在 `%APPDATA%/speakwise/speakwise-data/`

---

## 用户使用流程

1. 下载 `SpeakWise Setup.exe`
2. 安装 → 桌面出现 SpeakWise 图标
3. 打开 → 进入设置页 → 选择 DeepSeek → 输入 API Key → 验证 → 选择模型 → 保存
4. 在"个人知识库"填写简历
5. 在"岗位上下文"粘贴岗位 JD
6. 回到"对话"页 → 输入自我介绍 → AI 生成回答

---

## 注意事项

- 用户需要**自行获取** DeepSeek API Key（https://platform.deepseek.com）
- 首次启动需要联网验证 API Key
- 所有数据存储在 `%APPDATA%/speakwise/speakwise-data/`
- 如有端口冲突，修改 `frontend/src/lib/api.ts` 中的 `BASE_URL` 后重新打包

---

## 一键打包脚本（PowerShell）

```powershell
# build.ps1 — 一键构建所有组件
$ErrorActionPreference = "Stop"

Write-Host "=== 1/4 构建前端 ===" -ForegroundColor Cyan
cd frontend; npm run build; cd ..

Write-Host "=== 2/4 打包后端 ===" -ForegroundColor Cyan
pyinstaller --onefile --name speakwise-backend `
  --add-data "backend/src/prompts;prompts" `
  --hidden-import=sse_starlette --hidden-import=sqlmodel `
  --hidden-import=pypdf --hidden-import=docx --hidden-import=dotenv `
  --collect-all openai backend/src/main.py

Write-Host "=== 3/4 复制后端到 dist ===" -ForegroundColor Cyan
Copy-Item "dist/speakwise-backend.exe" "dist/speakwise-backend/" -Force

Write-Host "=== 4/4 Electron 打包 ===" -ForegroundColor Cyan
cd electron; npm run build; cd ..

Write-Host "=== 完成！===" -ForegroundColor Green
ls dist/*.exe
```
