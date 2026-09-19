# Rick PPT · PPTX Agent

[![PPTX LAB · 点击进入网站](https://rick-ppt.woodsy-crane-8759.chatgpt.site/og.png)](https://rick-ppt.woodsy-crane-8759.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rick-ppt.woodsy-crane-8759.chatgpt.site)**

一个内容优先的 Codex PowerPoint 插件和网站工作流：先调查与阅读，再写逐页大纲，制作原生可编辑的 PPTX，并在需要的区域加入可操作的 JSON 场景、代码编辑器和动画。独立上下文审核内容、静态页面和交互状态后再交付。

内容研究按任务需要投入精力，不固定时间或 token 比例。页面形式、字体、图片和分步呈现服从内容与观众需要，不强制套用固定模板。

插件源码位于 **[pptx-agent/](pptx-agent/)**，完整说明见 **[插件 README](pptx-agent/README.md)**，主流程见 **[SKILL.md](pptx-agent/skills/pptx/SKILL.md)**。

## 本地运行

需要 Python 3.11+、LibreOffice 和 Poppler。在仓库目录执行：

```bash
cd pptx-agent
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[interactive]'
.venv/bin/pptx --help
cd runtime
npm ci
npm run build
```

插件目录包含 `.codex-plugin/plugin.json`、`skills/` 和 `hooks/`；将 `pptx-agent` 作为插件目录使用。安装和 hooks 说明见插件 README。

## 仓库范围

`pptx-agent/` 包含插件、通用交互运行时、测试和必要资源；`workflow/` 包含持久日志与 Codex app-server 传输；`runner/` 包含隔离的制作执行端；`website/` 是可审查的网站源码快照。用户任务、账号凭证、运行日志和本地配置不上传。

网站支持制作中的聊天、修改意见、附件、版本下载和断点续做。恢复会验证检查点并创建新的工作目录，保留旧任务轨迹；交付前的新意见会使旧审核失效。运行说明见 [runner/README.md](runner/README.md)，逐项进度见 [执行清单](docs/interactive-runtime-plan.md)。

技术说明：[架构](docs/interactive-architecture.md)、[兼容性](docs/interactive-compatibility.md)、[PowerPoint 实测清单](docs/manual-powerpoint-verification.md)。

`blank.pptx` 是创建演示文稿所需的空白资源。导出会进行结构校验和实际渲染；静态渲染不能证明 PowerPoint 中的动画、视频或高级对象播放完全一致。
