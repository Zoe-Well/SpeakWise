# SpeakWise 启动说明

SpeakWise 由 FastAPI 后端、React/Vite 前端和 Electron 桌面壳组成。

## 环境要求

- Python 3.12
- Node.js 20+
- uv

以下命令以 PowerShell 为例。命令中明确使用 `npm.cmd` 和 `npx.cmd`，避免 Windows PowerShell 的执行策略拦截 `npm.ps1` 或 `npx.ps1`。

## 方式一：一键启动（推荐）

在项目根目录运行：

```powershell
.\start.ps1
```

脚本会依次完成环境检查、依赖同步、后端启动、前端启动，并打开浏览器。

- 前端：`http://localhost:5173`
- 后端：`http://127.0.0.1:8001`

## 方式二：手动启动（浏览器开发）

终端 1，在项目根目录启动后端：

```powershell
cd F:\AgentProjects\SpeakWise
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8001 --reload
```

终端 2，启动前端：

```powershell
cd F:\AgentProjects\SpeakWise\frontend
npm.cmd run dev
```

然后打开 `http://localhost:5173`。

前端默认连接 `http://127.0.0.1:8001`，因此不要只修改后端端口；如需使用其他端口，应同时设置前端的 `VITE_API_URL`。

## 方式三：Electron 启动

Electron 模式支持提词器悬浮窗。开发模式下仍需先启动 Vite 前端。

终端 1，启动前端：

```powershell
cd F:\AgentProjects\SpeakWise\frontend
npm.cmd run dev
```

首次使用时，在终端 2 安装 Electron 目录的依赖：

```powershell
cd F:\AgentProjects\SpeakWise\electron
npm.cmd install
```

然后从项目根目录启动 Electron。项目根目录的 `main.js` 是桌面主进程入口，Electron 会自动启动 `8001` 端口的后端：

```powershell
cd F:\AgentProjects\SpeakWise
$env:NODE_ENV="development"
.\electron\node_modules\.bin\electron.cmd .
```

不要从 `electron` 目录执行 `npx electron .`，否则使用的是该目录下的旧入口，而不是项目根目录的 `main.js`。

## 浏览器与 Electron 的区别

| 功能 | 浏览器 | Electron |
|---|---:|---:|
| 对话、知识库、JD、模板 | 支持 | 支持 |
| 提词器悬浮窗 | 不支持 | 支持 |
| 前端热更新 | 支持 | 支持，必要时手动刷新窗口 |

## 服务地址

| 服务 | 地址 |
|---|---|
| 前端页面 | `http://localhost:5173` |
| 后端 API | `http://127.0.0.1:8001` |
| Swagger 文档 | `http://127.0.0.1:8001/docs` |
| 健康检查 | `http://127.0.0.1:8001/api/health` |

## 停止服务

手动开发时，分别在前后端终端按 `Ctrl+C`。Electron 模式下关闭桌面窗口会同时停止它自动启动的后端。

使用一键脚本启动后，可运行：

```powershell
.\stop.ps1
```

注意：当前 `stop.ps1` 会终止系统中所有名为 `python` 和 `node` 的进程。如果同时运行其他 Python 或 Node.js 项目，请改为关闭对应终端，避免误停其他服务。
