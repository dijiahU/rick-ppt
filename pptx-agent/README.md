# PPTX Agent for Codex

[![PPTX LAB · 点击进入网站](https://rick-ppt.woodsy-crane-8759.chatgpt.site/og.png)](https://rick-ppt.woodsy-crane-8759.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rick-ppt.woodsy-crane-8759.chatgpt.site)**

当前流程：研究与理解内容 → 逐页内容大纲 → 选择原生/交互/混合呈现 → OOXML 与声明式场景制作 → 实际渲染和交互测试 → 独立内容与视觉审核 → 导出。
先决定说什么，再决定怎么呈现。主技能保留必要规则，细节按需读取。
内容参考：[内容研究](skills/pptx/references/content.md)；公式采用
[公式保真](skills/pptx/references/technical/formula-fidelity.md) 的专项核对，可运行只读 `inspect_formulas.py`。
搜索可用于事实、文学解读与视觉/模板参考；搜索不等于获得素材下载或复用权限。

原生页面使用 Direct OOXML。只有明确的 Content Add-in 区域使用共享的 JSON 场景运行时；页面上的原生文字、公式、图表和其他对象继续可编辑。普通页面不需要 Web 场景，用户文件不通过 python-pptx 重写。

## 安装与运行

macOS/Linux，Python 3.11+、LibreOffice 和 Poppler。macOS 可用 `brew install --cask libreoffice` 和 `brew install poppler`；Linux 安装发行版的 `libreoffice-impress`、`poppler-utils`。

在插件目录执行：

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/pptx --help
```

也可直接执行 `.venv/bin/python skills/pptx/scripts/pptx.py`。

```bash
.venv/bin/pptx unpack /project/paper.pptx
.venv/bin/pptx -w /project/.pptx-agent/paper list slides
.venv/bin/pptx -w /project/.pptx-agent/paper inspect 3
.venv/bin/pptx -w /project/.pptx-agent/paper find "Old title"
.venv/bin/pptx -w /project/.pptx-agent/paper refs ppt/slides/slide3.xml
# 使用编辑器直接修改 workspace/ppt/slides/slide3.xml
.venv/bin/pptx -w /project/.pptx-agent/paper validate
.venv/bin/pptx -w /project/.pptx-agent/paper render 3
# 查看命令返回的 PNG，检查排版
.venv/bin/pptx -w /project/.pptx-agent/paper diff --xml slide3
.venv/bin/pptx -w /project/.pptx-agent/paper export /project/paper-edited.pptx
```

`--workspace` 在子命令之前。省略时从 cwd 向上查找 active workspace；多个候选时要求显式选择。所有结构结果输出 JSON，XML diff 输出 unified diff，错误返回非零 exit code。

完整命令：`unpack`、`list`、`find`、`inspect`、`refs`、`render`、`validate`、`diff`、`snapshot`、`rollback`、`export`。`validate --level 1/2/3` 分别执行 XML、结构/引用、结构加真实渲染。`unpack --render` 可生成初始预览。

## 保真与保护

- 用户源文件从不作为输出目的地。备份 original.pptx 设为只读，并用 SHA-256 检查源文件和备份。
- 未修改的包内文件保留字节；ZIP 压缩、条目顺序和时间戳可能变化。
- ZIP 解压拒绝路径穿越、符号链接、重复/大小写冲突条目及超过限额的文件。
- 每次 export 都独立检查 XML、关系、内容类型、ZIP 和 LibreOffice 渲染。失败不发布新 PPTX；已有输出不覆盖，新文件以 `-2`、`-3` 编号。
- 导出在同一文件系统内用原子 link 发布，避免检查存在与写入之间的覆盖竞态；导出期间发生内容变化会失败并要求重试。
- snapshot 复制 workspace；rollback 会先保存被替换内容的恢复快照。普通校验错误不自动回滚。
- 渲染包括隐藏页，按演示文稿顺序编号。每次渲染保存独立 generation 目录，其路径由 JSON 返回，旧图不会被误当作新结果。

## Codex 插件

入口为 `.codex-plugin/plugin.json`，Skill 位于 `skills/pptx/`，hooks 自动从 `hooks/hooks.json` 发现。为了兼容当前插件校验器，manifest 不重复声明 `hooks` 字段。

本仓库提供插件源码；将其加入 local marketplace 后，在 Codex `/plugins` 中安装。安装后的插件路径也需具备上述 Python 依赖（在该插件根目录创建 `.venv`，或将 `PPTX_AGENT_PYTHON` 设为已安装依赖的 Python 绝对路径）。然后：

1. 启动新的 Codex session，让 bundled Skill 被发现。
2. 打开 `/hooks`，review PPTX Agent 的三个 hook 并 trust。
3. 通过 Skill 编辑现有 PPTX。

PreToolUse 拦截明显的原文件覆盖/删除，保存修改前 manifest，并为高风险 XML 或无法静态分析的 shell 写操作建立快照。PostToolUse 重新计算哈希并校验。Stop 发现 dirty workspace 后执行完整 export；连续失败两次阻断，第三次报告严重错误并保留 workspace/snapshots。

Hooks 是可绕过的 guardrail，不能静态证明任意 Python/shell 的所有副作用。它们不会自动获信任，也不能代替 export gate。接口依据：[Codex hooks](https://learn.chatgpt.com/docs/hooks)、[Codex plugins](https://learn.chatgpt.com/docs/plugins)。

## 边界

结构检查不是完整 ECMA-376 schema 验证。LibreOffice 渲染通过不能证明与 Microsoft PowerPoint 像素一致，也不能证明所有动画播放语义正确。未知扩展、SmartArt、OLE 等默认保留；高级对象的定向编辑需要 Agent 检查 XML 和对应软件表现。需要图像判断时由当前 Codex 查看 PNG，不调用额外模型服务。

旧版 Office VML 中存在非标准 XML 的条件包装标记（如 `<![if gte mso 9]>`）。校验器只在内存解析视图中移除成对标记，检查内部元素和关系，原始 VML 字节不改写。OLE 内嵌预览图片的 ID 不与 slide 顶层 shape ID 混算；`mc:Choice`/`mc:Fallback` 作为互斥分支处理。

## 内容与审核

主技能收敛为：调查与阅读 → 逐页内容大纲 → 原生页面制作 → 独立内容/视觉审核。优先把精力用于内容研究、解释和组织，根据任务需要决定深度，不规定固定时间或 token 比例。宿主用量记录仅用于观察，不能当作质量评分或验收门槛，也不能用重复阅读或等待冒充有效研究。无资料缺口的小修改不走完整流水线。

网站通过 outline.json 展示演示目标、章节、每页标题和实际内容摘要；修改大纲时使受影响预览失效，避免旧图配新内容。审核者使用新的独立上下文，内容先盲看成品，再核对需求和证据；视觉结合全页图、整套节奏和原生动画结构。审核绑定具体交付文件。

使用原生 OOXML 制作页面，字体、图片、留白、节奏与动画由内容需要决定，不规定每几页必须一图或套用固定版式。新建空白文件位于 skills/pptx/assets/blank.pptx。

辅助脚本 native_builds.py（语义分组原生出现动画）和 review_packet.py（审核文本、整套缩略图、媒体与动画事实）。静态渲染不认证 PowerPoint 播放；必须保留该验证边界。

插件目录分发源码、技能参考、必要资源、hooks 与通用交互运行时。外层仓库还包含脱敏的网站、执行端和测试源码；本地配置、凭证、用户任务和运行轨迹不进入公开源码。

## 交互运行时

在插件目录安装浏览器依赖，再构建共享运行时：

```sh
.venv/bin/python -m pip install -e '.[interactive]'
.venv/bin/python -m playwright install chromium
cd runtime
npm ci
npm run build
cd ..
.venv/bin/pptx interactive cert install
.venv/bin/pptx interactive doctor
```

`cert install` 使用本机开发证书和用户钥匙串；凭证、私钥不属于演示文稿。
`interactive validate-spec` 检查场景；`attach/update/render` 生成实际测试与静态预览；
`interactive bundle OUTPUT --zip` 创建新的独立目录及 ZIP，包含 PPTX、场景、资源、运行时、清单与启停脚本。已有输出不覆盖。

运行时提供原语、布局、状态、表达式、事件、拖拽、时间线、计算、图表、表格和 GeoJSON。
Monaco/Pyodide、Three、ONNX、MapLibre、KaTeX 按声明延迟加载。
代码编辑器可运行隔离的短 JavaScript/Python 实验；教学数值必须通过实际输入/输出测试。

阅读 [创作指南](skills/pptx/references/interactive-authoring.md)、
[运行时说明](skills/pptx/references/interactive-runtime.md) 和
[审核指南](skills/pptx/references/interactive-review.md)。实际支持范围见
[兼容性矩阵](docs/interactive-compatibility.md)。浏览器通过和原生静态渲染通过分别记录；
PowerPoint 编辑、放映和保存重开必须在目标软件单独验证。
