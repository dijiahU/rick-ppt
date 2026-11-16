# 此服务器的 Rick PPT 执行端

本目录是服务器运行入口。本地开发使用独立 checkout 与 `tools/environment.py`，
参见 [本地与服务器环境隔离](../docs/environments.md)。不要把服务器私密配置复制到 Mac 开发目录。

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
- 已验证的插件快照：`runner/runtime/0.1.0+codex.20261115pagepreview2/pptx-agent/`。不要在任务运行期间改这个快照；更新时另行暂存、验证，再温和重启。
- 固定的 Codex：`deploy/libexec/codex-0.162.1/`，由官方 npm 平台包安装并核对 SHA-512。`deploy/bin/codex` 指向该副本，避免桌面应用升级清理缓存后破坏接单。
- 网络：服务器 Mihomo 的 `127.0.0.1:7890`。`keep_proxy.py` 使用已经运行的服务；端口没有服务时，读取服务器私密配置启动 Mihomo。配置中的远端节点没有依赖 Mac 的回环转发。
- 网站接口连接：此服务器的私密配置启用 `site_http_transport: "pooled"`、`site_http_proxy: "http://127.0.0.1:7890"`，由主机 Python 复用通过代理建立的 HTTPS 连接。每个线程独立连接，空闲 45 秒后关闭；请求仍有超时、大小限制和 TLS 证书校验，不跟随重定向。断线后不会自动重发领取任务；原有续租期限和可安全重复操作的有限重试规则保留。未设置该选项的执行端继续使用原 curl 路径。
- 本机实际限制为 0.5 CPU、2 GiB 内存；接单并发设为 1，私密配置中的 `parallel_reviews: false` 让独立审核依次执行，以降低内存峰值。正常制作和排队仍需要时间。

## Linux 适配

此 AutoDL 容器不能创建 Bubblewrap/Docker 所需的命名空间。任务命令改用 Landlock、seccomp 和独立 UID 隔离，只允许修改自己的临时工作区，禁止任务直接创建网络套接字、读取其他任务和主机私密文件。`deploy/bin/bwrap` 是 Codex 的适配入口，不是完整 Bubblewrap；只接受受限 PPTX 工作区的调用，其他情况拒绝执行。

LibreOffice 使用独立的临时用户目录和受限的本地通信路径。`office_tmp.c` 处理 LibreOffice 7.3 的共享临时目录探测；重新安装时可用以下命令生成配套库：

```bash
gcc -shared -fPIC -O2 -o deploy/office_tmp.so deploy/office_tmp.c
```

媒体解码也在 Linux 隔离下运行。XML 解析通过本项目 venv 的 `sitecustomize.py` 加载与 Conda Python 配套的 Expat，未修改 MateConv 环境。

Linux 的 Office 转换时限为 120 秒，任务端等待回复为 180 秒，原生调用及 PNG 转换的外层预算为 210 秒；未配置的独立插件仍使用原生默认时限。避免外层先于内层退出后重复提交转换。

Office 的线程池按当前容器的 `cpu.max` 和进程允许的 CPU 数量取较小值，向上取整并至少保留一个线程，通过 `MAX_CONCURRENCY` 传入。此机器为 0.5 CPU，因此使用一个工作线程，避免按宿主机的 80 核启动线程池。变量的行为见 [LibreOffice 7.3 线程池实现](https://github.com/LibreOffice/core/blob/libreoffice-7-3/comphelper/source/misc/threadpool.cxx)。字体校验和暂存结束后释放原始字体缓冲、收集字体解析器的无用对象，并在 Linux 上将可释放的主机堆内存归还给系统，再启动 Office；私有字体目录使用文件复制，避免额外创建整份字体的 Python 字节缓冲；保留原有字体字节、字体检查和隔离限制。这些措施降低资源压力，不能单独证明异常终止的根因已经解决。

每次 LibreOffice 转换使用单独的工作目录、用户身份和本地通信路径；不再复用一个固定渲染用户。转换保留父进程的续租与 120 秒时限，并仅对启动返回码 81 和一次异常中断执行有限重试；异常中断后的重试使用新的 LibreOffice 用户配置，保留此前配置供排查。已使用同一份实际 10 页输入完成隔离转换并核对 PDF 页数。

渲染回复先写入任务用户拥有的私密临时文件，再原子发布，成功和失败回复均使用同一流程；正在等待的任务进程可以直接读取，无需下一条命令重新调整所有权。Linux 默认字体从真实安装的 DejaVu Serif 和 Noto Serif CJK SC 建立来源及校验记录，并复制到任务中，渲染时继续校验字体与来源文件。冻结稿件和独立审核先复制作者已验证的原始字体文件，再补充缺少的默认字体，避免同名字体的不同提取字节触发一致性错误。主机作者提示、审核提示和插件文档统一读取 Linux 字体基线；用户明确指定的字体、模板和播放环境仍优先。策略更新使用新的插件版本和正常恢复流程，不修改旧审核结果。恢复时也会刷新逐页预览工具和交互支持的插件路径，避免升级后仍调用任务中保存的旧目录。

任务命令重复进入隔离时，已正确交接的文件不再重复 `chown`，避免无内容变化的元数据更新打断恢复点保存。捕获中恰好发生的文件变化最多重新打开并校验三次；持续变化时保留先前恢复点，原有记录损坏仍直接拒绝。输出进展计数绑定每次经授权重新领取的运行 ID，同一运行内的停滞保护继续保留。

## 已执行的验证

- 真实 Codex 会话：命令执行、文件编辑与图片查看。
- 合成 canary 隔离检查：独立 UID、外部读写、符号链接逃逸、主机权限修改、截断、提权、Unix/IPv4/IPv6 套接字拒绝；工作区写入及同目录重命名正常。
- 原生工具测试：111 项通过；其中适合在任务隔离内运行的 110 项也通过，另 1 项需要读取主机契约文件，在主机侧验证。
- 审核恢复测试 54 项、结构化输出测试 7 项、原 Mac 渲染就绪测试 9 项通过；另实测 Linux 超时不会尝试 Docker Desktop。
- 两页中文 PPT 经过真实制作、PDF/PNG 渲染、独立内容及视觉审核和交付校验。结果：`/root/autodl-tmp/rick-ppt-smoke-2-slides.pptx`；完整收据在 `deploy/private/smoke-receipt.local.json`。
- Sites 的线上 Worker 表已收到服务器的 `codex` 能力心跳；公网首页返回 HTTP 200。
- 网站接口连接复用：本地真实 TLS/断线安全测试 14 项、原 HTTP 恢复测试 18 项和会话测试 40 项通过；改进上线后，连续 10 次真实接口心跳均成功。这是短时网络检查，不代表已完成中断用户任务的重新交付。
- 渲染交接修复：4 项主机/任务 UID 测试、3 项渲染输入测试和 13 项字体测试通过；在正式服务的 0077 文件设置下，以隔离任务用户完成实际封面 PDF 和 PNG 预览，验证回复与输出文件可读。
- 快照与恢复修复：56 项日志/恢复点测试、33 项执行连续性测试、4 项 Linux 所有权测试及实际隔离边界检查通过。
- 字体与审核策略：14 项字体测试、2 项主机字体契约测试和 54 项审核会话恢复测试通过；真实独立审核工作区保留了作者两份字体的校验值。
- 渲染内存与 CPU 配额：5 项字体缓冲/渲染交接测试、9 项转换重试及容器 CPU 配额测试通过。
- 可选设计调整的恢复保留 `source_hash` 和渲染环境，并校验保存文件的哈希；32 项设计恢复测试通过。旧恢复记录缺少绑定时仍不伪造画布预览证据。
- 对常驻进程发出温和退出信号后，Supervisor 自动启动新进程，新进程再次通过隔离自检并进入 `ready`；收据在 `deploy/private/restart-check.local.json`。

两页测试的最终文件保存在本地，没有创建真实用户任务或消耗网站提交额度，也没有代替用户完成浏览器登录提交。原网站的认证、领取、续租和上传接口继续保留。静态渲染不代表已经验证 PowerPoint/WPS 的实际幻灯片播放。

审核报告中内容修正与展示优先级的字段冲突，允许同一完成审核上下文内进行一次格式纠正；原有问题、严重程度、依据和内容修正路径必须保留。没有完整逐页覆盖或审核未完成时仍拒绝复用。

Codex 标准输入输出使用 64 KiB 缓冲；接收队列保留 4096 条上限，队列满时等待消费者，避免主机保存检查点或渲染超过一秒就误判会话损坏。非法或过大的帧仍拒绝，错误只输出分类和退出码。Linux 渲染预算也通过主机进程和任务工具两层环境白名单传递。

独立审核中，只有确认审核进程被 SIGKILL 后，才最多自动重试两次。每次创建新的隔离审核目录与会话，重新核对冻结输入，保留未完成记录，并按原规则复用已经验证的完整报告；原有任务总时限、用户停止与修订、租约检查及所有审核标准继续生效。其他进程退出、尚未确认进程结束的断线、作者操作和交付请求不走这条重试路径。

## 任务计时与性能限制

运维测试入口为 `/api/worker/benchmarks`，需要原有 Worker 令牌；使用独立系统身份、独立额度和请求幂等键，不冒充网站用户。接口可提交并查询测试任务；重试使用原有任务的失败时间戳作为条件，同一任务的最初创建时间继续作为总计时起点。

已验证新版渲染器的 Linux 执行端，`pptx.py -w WORKSPACE render N` 使用 PDF `PageRange=N`，只输出目标页的一页 PDF 和 `slide-N.png`，保留原页码、整稿来源哈希及页面预览记录。实际输出必须恰好一页，否则明确失败；不会把整稿第一页当成目标页。整稿预览、最终导出和独立审核仍输出完整稿件。Office 仍需启动、读取整份输入和共享资源，单页输出不会消除这部分成本。每次结果另存 `render-timings.json`，记录 PDF 请求、PNG 转换及主机 Office 转换耗时；耗时不参与审核环境一致性判断。在 0.5 CPU、2 GiB 且存在其他进程的实例上，制作速度和异常恢复时间必须按实测报告。不得将进程被 SIGKILL 直接认定为内存不足或网络故障；截至本轮排查，观察到了强制终止，但内存控制组没有记录 OOM kill，具体终止来源尚未确认。

## 运维边界

SSH 或 Codex 对话断开后，进程继续运行。服务器实例关机、网络中断或登录失效时，制作无法持续进行；程序会对可恢复的网络故障重试。开机入口已配置，整台实例的断电重启尚未为了测试而执行。

任务状态、检查点、素材和日志会占用磁盘，应定期检查 `df -h /root/autodl-tmp`。日志已配置轮转；没有自动删除用户成果。历史任务保存在 Mac 上的私密检查点没有随公开 Git 仓库迁移，精确续跑这些旧任务需要另行转移对应状态。

私密配置、令牌、运行日志、任务成果、二进制运行包和临时状态都已在 Git 忽略规则中排除。不要把这些文件上传到公开仓库。

## 安装与验证单页渲染器

系统自带 LibreOffice 7.3 不支持本功能所需的命令行 JSON `PageRange`。安装官方版本至独立目录，不覆盖系统 Office；版本、下载地址和 SHA-256 固定在 `deploy/libreoffice-renderer.lock.json`。先下载该文件指定的归档，再执行：

```bash
.venv/bin/python deploy/install_renderer.py --archive /path/to/LibreOffice_26.2.7_Linux_x86-64_deb.tar.gz --destination deploy/libexec/libreoffice-26.2.7
.venv/bin/python runner/verify-renderer.py --prefix deploy/libexec/libreoffice-26.2.7/opt/libreoffice26.2
```

验证工具使用与生产相同的独立 UID、Landlock/seccomp 和 Office 调用方式，对两页样例请求第 2 页，检查 PDF 页数和实际文字。通过后才写入能力凭据。验证失败不会激活新版。排空正在处理的任务后，将 `deploy/libexec/libreoffice-current` 链接到已验证的 `opt/libreoffice26.2` 目录，暂存新插件快照并重启执行端。未安装链接的 Linux 执行端及未启用能力的独立插件保留原预览方式。

能力开关 `PPTX_RENDER_PAGE_RANGE=1` 由主机根据验证凭据设置，通过执行进程和任务工具的两层环境白名单传递。渲染代理仅接受一个合法页码及既有隐藏页选项，拒绝范围、越界页和其他导出参数；完整 PPTX 仍按原规则冻结、校验和隔离。Office 的官方参数说明见 https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html 。

单页功能的实测样例为相同的 15 页季度汇报和相同字体文件：整稿输出 15 页；指定第 4、13 页分别只输出一页 PDF 和对应原页码 PNG。第 4 页像素完全一致；第 13 页提取文字完全一致，文字边界最大差异约 0.328 pt（100 dpi 下约 0.455 像素），有少量像素差异，并非严格像素一致。完整测试报告、耗时及初始异常终止记录保存于服务器 `/root/autodl-tmp/rick-ppt-single-page-test.json`；单次结果随机器已有负载变化，不能作为固定性能承诺。

动画审核状态图也使用相同的逐页预览能力：某个状态槽只有一页需要检查时，仅请求该原页码；若多页共享状态槽，保留一次整稿批量转换。初始、中间和最终揭示前的状态、完整稿件来源、原始页码及冻结输入不变；不通过取消状态检查来缩短耗时。
