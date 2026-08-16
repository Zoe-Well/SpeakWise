# SpeakWise 发布与部署

## Windows 桌面安装包

桌面版把 Vite 前端、Electron 和 PyInstaller 后端一起打入 NSIS 安装包。用户数据保存在 Electron `userData/speakwise-data`，API Key 由用户在应用内配置。

```powershell
.\build.ps1
```

构建结果位于 `dist/`：

- `SpeakWise Setup 0.1.0.exe`：Windows 安装包；
- `win-unpacked/`：免安装调试目录；
- `speakwise-backend.exe`：仅后端构建产物。

发布前应在未安装 Python、Node.js 的 Windows 环境验证安装、启动、API Key 配置、对话和悬浮提词器。

## GitHub + Railway 单用户 Web 演示

Railway 使用根目录 `Dockerfile` 构建。容器会先构建 Vite，再由 FastAPI 同源提供前端和 API。

Railway Variables：

| 变量 | 必填 | 说明 |
|---|---|---|
| `APP_BASIC_AUTH_USER` | 是 | 浏览器访问用户名 |
| `APP_BASIC_AUTH_PASSWORD` | 是 | 使用随机强密码 |
| `SPEAKWISE_DATA_DIR` | 是 | 设置为 `/data` |
| `DEEPSEEK_API_KEY` | 否 | 推荐进入网页后配置，不提交到 GitHub |

在 Railway 为服务添加 Volume 并挂载到 `/data`，否则 SQLite、上传附件和设置会在重新部署后丢失。

当前 Web 部署是受密码保护的单用户演示版。不要移除 Basic Auth 后公开使用，因为当前数据库和 API Key 尚未按用户隔离。

## 阿里云域名

1. 在 Railway 服务的 **Settings → Networking → Custom Domain** 添加子域名，例如 `app.example.com`。
2. Railway 会给出一个 DNS 目标地址。
3. 在阿里云 DNS 添加 `CNAME`：主机记录填 `app`，记录值填 Railway 给出的目标。
4. 等待 DNS 生效和 Railway 自动签发 HTTPS 证书。

自定义域名只改变访问地址，不会把 Railway 服务迁移到中国大陆，也不能保证国内线路质量。
