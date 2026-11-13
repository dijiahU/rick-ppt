# 此服务器的 Rick PPT 执行端

网站继续使用 https://rickppt.aaarickmorty.chatgpt.site 。网页、登录、数据库和下载文件由 Sites 托管；本机常驻进程通过 HTTPS 领取任务，调用服务器已登录的 Codex，生成原生 PPTX，渲染并审核，再通过原有 Worker API 回传。用户的新任务不再依赖 Mac 开机。

## 启动与检查

在 AutoDL 终端执行：

```bash
cd /root/autodl-tmp/rick-ppt
bash deploy/start.sh
bash deploy/status.sh
tail -n 30 deploy/logs/worker.log
```

`start.sh` 可重复执行。正常状态是 `pptx-worker` 和 `pptx-proxy` 都显示 `RUNNING`；最新的 `runner/runtime-*.local.json` 应显示 `status: ready`。后台进程由本项目独立的 Supervisor 管理，配置是 `deploy/supervisord.conf`。自动启动入口已追加到 `/etc/autodl.sh`，与 AutoDL 原有 Jupyter、SSH 服务分开管理。

进程意外退出会自动重启。需要温和加载更新时，停止领取新任务并等当前任务完成：

```bash
/root/miniconda3/bin/supervisorctl -c deploy/supervisord.conf signal TERM pptx-worker
```

Supervisor 会在进程退出后启动新进程。不要为了更新强制杀死正在制作的任务。

## 本机配置

- 私密连接参数：`runner/settings.local.json`，权限为 600；其中令牌对应 Sites 的 `WORKER_TOKEN`。迁移时已切换该令牌，旧 Mac 执行端不再有接单权限。
- Python 环境：`.venv/`，与 MateConv 环境分开。
- 已验证的插件快照：`runner/runtime/0.1.0+codex.20261106surfacecheck2/pptx-agent/`。不要在任务运行期间改这个快照；更新时另行暂存、验证，再温和重启。
- 固定的 Codex：`deploy/libexec/codex-0.162.1/`，由官方 npm 平台包安装并核对 SHA-512。`deploy/bin/codex` 指向该副本，避免桌面应用升级清理缓存后破坏接单。
- 网络：服务器 Mihomo 的 `127.0.0.1:7890`。`keep_proxy.py` 使用已经运行的服务；端口没有服务时，读取服务器私密配置启动 Mihomo。配置中的远端节点没有依赖 Mac 的回环转发。
- 本机实际限制为 0.5 CPU、2 GiB 内存；接单并发设为 1。正常制作和排队仍需要时间。

## Linux 适配

此 AutoDL 容器不能创建 Bubblewrap/Docker 所需的命名空间。任务命令改用 Landlock、seccomp 和独立 UID 隔离，只允许修改自己的临时工作区，禁止任务直接创建网络套接字、读取其他任务和主机私密文件。`deploy/bin/bwrap` 是 Codex 的适配入口，不是完整 Bubblewrap；只接受受限 PPTX 工作区的调用，其他情况拒绝执行。

LibreOffice 使用独立的临时用户目录和受限的本地通信路径。`office_tmp.c` 处理 LibreOffice 7.3 的共享临时目录探测；重新安装时可用以下命令生成配套库：

```bash
gcc -shared -fPIC -O2 -o deploy/office_tmp.so deploy/office_tmp.c
```

媒体解码也在 Linux 隔离下运行。XML 解析通过本项目 venv 的 `sitecustomize.py` 加载与 Conda Python 配套的 Expat，未修改 MateConv 环境。

## 已执行的验证

- 真实 Codex 会话：命令执行、文件编辑与图片查看。
- 合成 canary 隔离检查：独立 UID、外部读写、符号链接逃逸、主机权限修改、截断、提权、Unix/IPv4/IPv6 套接字拒绝；工作区写入及同目录重命名正常。
- 原生工具测试：111 项通过；其中适合在任务隔离内运行的 110 项也通过，另 1 项需要读取主机契约文件，在主机侧验证。
- 审核恢复测试 53 项、结构化输出测试 7 项、原 Mac 渲染就绪测试 9 项通过；另实测 Linux 超时不会尝试 Docker Desktop。
- 两页中文 PPT 经过真实制作、PDF/PNG 渲染、独立内容及视觉审核和交付校验。结果：`/root/autodl-tmp/rick-ppt-smoke-2-slides.pptx`；完整收据在 `deploy/private/smoke-receipt.local.json`。
- Sites 的线上 Worker 表已收到服务器的 `codex` 能力心跳；公网首页返回 HTTP 200。
- 对常驻进程发出温和退出信号后，Supervisor 自动启动新进程，新进程再次通过隔离自检并进入 `ready`；收据在 `deploy/private/restart-check.local.json`。

两页测试的最终文件保存在本地，没有创建真实用户任务或消耗网站提交额度，也没有代替用户完成浏览器登录提交。原网站的认证、领取、续租和上传接口继续保留。静态渲染不代表已经验证 PowerPoint/WPS 的实际幻灯片播放。

## 运维边界

SSH 或 Codex 对话断开后，进程继续运行。服务器实例关机、网络中断或登录失效时，制作无法持续进行；程序会对可恢复的网络故障重试。开机入口已配置，整台实例的断电重启尚未为了测试而执行。

任务状态、检查点、素材和日志会占用磁盘，应定期检查 `df -h /root/autodl-tmp`。日志已配置轮转；没有自动删除用户成果。历史任务保存在 Mac 上的私密检查点没有随公开 Git 仓库迁移，精确续跑这些旧任务需要另行转移对应状态。

私密配置、令牌、运行日志、任务成果、二进制运行包和临时状态都已在 Git 忽略规则中排除。不要把这些文件上传到公开仓库。
