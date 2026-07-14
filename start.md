🏗️ 项目概览
SpeakWise — 智能面试助手（Interview Copilot），三件套桌面应用：


SpeakWise/
├── backend/src/          # Python FastAPI 后端（8 个 API 路由模块）
│   ├── api/              # profile, sessions, generate, templates, documents, settings, voice, jd
│   ├── db/               # SQLite 数据库
│   ├── llm/              # DeepSeek-V4-Pro 大模型调用
│   └── services/         # 业务逻辑层
├── frontend/             # React 18.3 + Vite + Tailwind CSS + shadcn/ui
├── electron/             # Electron 32 桌面壳
└── data/                 # 本地 SQLite 数据库文件
🚀 启动命令

方式一：一键启动（PowerShell，推荐）

.\start.ps1
自动完成：环境检测 → 依赖同步 → 启动后端 (8000) + 前端 (5173) → 打开浏览器

方式二：手动分步启动（浏览器开发）

终端 1 — 启动后端（Python FastAPI，默认端口 8000，被占用可换 8001）：

cd f:/AgentProjects/SpeakWise
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8000 --reload

终端 2 — 启动前端（Vite dev server，端口 5173）：

cd f:/AgentProjects/SpeakWise/frontend
npm run dev

然后浏览器打开 http://localhost:5173

方式三：Electron 启动（支持 📋 提词器悬浮窗）

终端 1 — 启动前端 Vite：

cd f:/AgentProjects/SpeakWise/frontend
npm run dev

终端 2 — 启动 Electron（自动拉起后端 + 打开桌面窗口）：

cd f:/AgentProjects/SpeakWise/electron && npm install    # 首次需要安装 Electron 依赖
npx electron .    # 从 electron/ 目录下运行

浏览器开发 vs Electron 区别：

功能	浏览器	Electron
对话/知识库/JD/模板	✅	✅
📋 提词器悬浮窗	❌	✅
DevTools 调试	✅ F12	✅ 自动打开
热更新	✅	⚠ 需手动刷新

提词器使用：
1. Electron 窗口中，对话页工具栏右侧点 📋 提词器
2. 半透明悬浮窗出现，AI 回答自动同步
3. 顶部紫色横条：悬停显示控件（播放/速率/字号/透明度），拖拽移动
4. 正文区鼠标穿透，不干扰背后窗口操作
5. 所有设置（位置/大小/速率/字号/透明度）自动记忆

停止服务

.\stop.ps1      # PowerShell
或


stop.bat        # CMD

强制杀死占用后端进程
如果停止脚本失效，端口仍然被占用，可以用以下命令强制杀死占用 8000 端口的进程。
PowerShell（杀进程 + 检测僵尸套接字）：
```powershell
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if (-not $conn) { Write-Host "端口 8000 空闲" }
else {
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $conn.OwningProcess -Force
        Write-Host "已杀死进程 $($proc.ProcessName) (PID $($conn.OwningProcess))"
    } else {
        Write-Host "⚠ 僵尸套接字：PID $($conn.OwningProcess) 进程已不存在但端口仍被占用。"
        Write-Host "  → Windows bug，无法直接清除。建议：改用端口 8001 启动后端。"
    }
}
```
CMD：
```cmd
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8000.*LISTENING') do taskkill /F /PID %a 2>nul || echo 无法杀进程，可能是僵尸套接字，换端口 8001 启动
```

僵尸套接字（端口杀不掉）


当 `netstat -ano` 显示端口 LISTENING 但 `taskkill` 报"找不到进程"时，说明是 Windows 的 TCP 僵尸连接。

方案一：TCPView 强制关闭（推荐，无需重启）
从微软 Sysinternals 下载 TCPView（绿色免安装）：
https://learn.microsoft.com/en-us/sysinternals/downloads/tcpview
管理员权限运行，找到 `127.0.0.1:8000` 的条目，右键 → Close Connection。
或用命令行版：
```powershell
# 下载（仅首次）
Invoke-WebRequest -Uri "https://live.sysinternals.com/Tcpvcon64.exe" -OutFile "$env:TEMP\tcpvcon64.exe"
# 关闭连接
& "$env:TEMP\tcpvcon64.exe" /close 127.0.0.1 8000
```

方案二：禁用再启用网卡（不重启系统）
```powershell
# 管理员权限运行
Get-NetAdapter | Where-Object Status -eq "Up" | Disable-NetAdapter -Confirm:$false
Start-Sleep 3
Get-NetAdapter | Where-Object Status -eq "Disabled" | Enable-NetAdapter
```
这会清空所有 TCP 连接，相当于网络层面的"重启网卡"。不影响其他程序，但会短暂断网 ~5 秒。

方案三：一劳永逸——uvicorn 配置 SO_REUSEADDR
在 `backend/src/main.py` 的 uvicorn 配置中加上 `reuse_port=True`，之后即使有 TIME_WAIT 或僵尸连接也能绑定成功。这样彻底不依赖杀端口。

方案四：临时换端口
后端改用端口 8001 启动，改 `api.ts`：
```powershell
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8001 --reload
```
```ts
// frontend\src\lib\api.ts
const BASE_URL = "http://127.0.0.1:8001";
```

服务地址
服务	地址
前端页面	http://localhost:5173
后端 API	http://127.0.0.1:8000（或 8001）
Swagger 文档	http://127.0.0.1:8000/docs（对应端口）
健康检查	http://127.0.0.1:8000/api/health（对应端口）
Electron 桌面	自动打开，内部加载 http://localhost:5173
