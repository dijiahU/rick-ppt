# 本地开发与服务器运行

共用 `main` 上的设计流程、原生工具与网站代码，分开代码 checkout、私密配置、
依赖、运行快照、任务状态和启动入口。不要建立长期各改各的“Mac 产品分支”与
“Linux 产品分支”。功能在开发分支验证后合回 `main`；服务器部署指定提交。

| 项目 | 本地开发 | 服务器生产 |
|---|---|---|
| 代码目录 | 独立工作区，例如 `rick-ppt-local/` | `/root/autodl-tmp/rick-ppt` |
| 配置标记 | `deployment_environment: local` | `deployment_environment: server` |
| 网站/任务队列 | `http://127.0.0.1:3000`，本地模拟账号 | 已部署的 Sites HTTPS 网站 |
| 凭证 | 新生成的开发凭证，匹配本地 `.dev.vars` | 服务器原有私密凭证；不复制到开发机 |
| 数据 | 本 checkout 的 `.wrangler/`、`runner/state/local` | 线上 D1/R2、服务器独立检查点 |
| 运行快照 | 本 checkout 的 `runner/runtime/` | 服务器 checkout 的 `runner/runtime/` |
| 依赖 | 本地 `.venv`、`website/node_modules` | 服务器 `.venv` 与 `deploy/libexec` |
| 启动 | `tools/environment.py start-local` | `bash deploy/start.sh`，Supervisor |
| 电源策略 | 启动入口启用原有“插电运行”策略 | Linux 常驻，不依赖 Mac 电源 |

“本地/服务器”表示执行环境，不是模型收费来源。模型及其账号仍由原有模型配置选择，
不会因为环境标记自动改用 API 或另一份订阅。两种平台的字体、渲染器和浏览器能力
可能不同；此次隔离不承诺像素一致，也不改变设计/审核标准。

## 建立本地工作区

从已有仓库创建一个开发 worktree，保留旧运行目录：

```bash
git fetch origin
git worktree add -b dev/my-change /absolute/path/rick-ppt-local origin/main
cd /absolute/path/rick-ppt-local
python3.11 -m venv .venv
.venv/bin/python -m pip install -e './pptx-agent[test]'   # test extra: python-pptx for runner tests
.venv/bin/python tools/environment.py init-local
.venv/bin/python tools/environment.py check local
```

`init-local` 不读生产凭证、不联网、不启动 worker 或模型。它生成新的开发 token、
独立初始插件副本，以及权限为 600 的 `runner/settings.local.json`、
`runner/deployment.local.json`、`website/.dev.vars`。遇到已有配置直接停止，绝不覆盖。
`--port` 可指定测试网站端口；网站启动时必须使用相同端口。

本地网站第一次启动前，安装其依赖并初始化本地数据库：

```bash
cd website
npm ci
npx wrangler d1 execute DB --config scripts/local-db.json --local --persist-to .wrangler/state --file drizzle/0000_absurd_mongoose.sql
npx wrangler d1 execute DB --config scripts/local-db.json --local --persist-to .wrangler/state --file drizzle/0001_misty_tyger_tiger.sql
npm run dev -- --host 127.0.0.1 --port 3000
```

迁移命令只用于新本地数据库，逐个执行一次，不加 `--remote`。Vite 已使用模拟
D1/R2 绑定和项目内持久化；`.dev.vars` 供本地 Cloudflare 绑定读取。开发登录是
Sites 的模拟账号，不是线上用户。完整网站启动、登录和生成仍需在实际开发机验收。

网站准备好后，另开终端从仓库根目录启动本地 worker：

```bash
.venv/bin/python tools/environment.py start-local
```

此入口清除旧终端继承的 worker 路径、模型 profile 和上下文覆盖；保留模型网络代理，
但本地队列请求明确绕过代理。它复用现有启动器、Docker 渲染就绪检查和电源策略。
检查输出的 `configuration_valid` 只说明配置有效，不等同服务在线、模型可用或端到端成功。

运行中的作者使用暂存插件。修改 Skill 后按原有 `runner/stage-runtime.py` 流程，
为新快照更新插件版本并完成自检，再用 `start-local --reload` 温和切换。
修改 runner 本身应先让当前任务结束，再启动新版；不要让开发热编辑影响正在制作的任务。

## 服务器采用同一版本

现有部署见 [deploy/README.md](../deploy/README.md)。首次采用环境标记时，在服务器
原有私密配置中增加 `"deployment_environment": "server"`，保留原有凭证和依赖路径。
`plugin` 与 `state_directory` 应在该服务器 checkout 的 `runner/` 内；
[示例](../deploy/server-settings.example.json) 只描述结构，不能直接替换现有配置。

```bash
cd /root/autodl-tmp/rick-ppt
.venv/bin/python tools/environment.py check server
bash deploy/status.sh
```

更新流程：本地验证 → 合入 `main` → 选定提交 → 等活动任务排空 → 更新服务器源码并
暂存新插件 → 检查配置/隔离/渲染 → 温和启动 → 检查新进程的 runtime 收据和心跳。
保留旧提交、旧插件和原始已审核交付文件，才能回退或只重传。不要在开发命令中
自动 SSH、pull、重启或发布网站；GitHub、网站和 worker 是不同的发布对象。

旧部署未标记时仍可使用原 HTTPS 路径；升级不会自动改掉已有账号、队列或运行服务。
已创建本地标记的工作区则拒绝未标记或 server 配置，即使来自终端继承的设置路径。
标记和路径检查用于防止操作混用，不替代已有任务隔离和服务器权限控制。

## 本次工作区

2026-11-16 创建的 Mac 开发目录是 `/Users/rick/Desktop/ppt/rick-ppt-local`，
基线 `50b8520`，开发分支 `dev/local-server-isolation`。原 Mac 运行目录
`.work/interactive-runtime-20260920/repo` 保持 `e590f7d`，未改动其配置和自动启动服务。
此分支是一次隔离改动的开发分支，验证后合入 `main`，不是第二条长期产品线。

若要退休旧 Mac 接单服务，应另外检查并调整它的 LaunchAgent/watchdog；复制代码或
新建开发目录不会自动停止旧进程。不要把旧线上 worker token 复制到开发配置。
