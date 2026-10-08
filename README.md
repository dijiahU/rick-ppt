# Rick PPT · PPTX Agent

[![PPTX LAB · 点击进入网站](https://rickppt.aaarickmorty.chatgpt.site/og.png)](https://rickppt.aaarickmorty.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rickppt.aaarickmorty.chatgpt.site)**

一个内容优先的 Codex PowerPoint 插件和网站工作流：研究来源、规划内容与视觉表达，按页顺序制作原生可编辑的 PPTX，使用独立上下文并行审核内容和视觉，交付审核对应的单个文件。原生点击揭示、触发动画、内部导航和内嵌媒体可用，观看者无需额外安装交互运行环境。

内容研究按任务需要投入精力，不固定时间或 token 比例。页面形式、字体、图片和分步呈现服从内容与观众需要，不强制套用固定模板。

需要视觉表达时，在制作前按需在线搜集并查看高质量参考，灵感可以来自任意相关艺术形式；简洁的信息传达采用足够清晰的表达。视觉审核检查风格与内容、用途、受众和观看方式的适配及整套一致性。具体规则见 [设计检索](pptx-agent/skills/pptx/references/research-and-assets.md)和[视觉审核](pptx-agent/skills/pptx/references/visual-review.md)。

插件源码位于 **[pptx-agent/](pptx-agent/)**，完整说明见 **[插件 README](pptx-agent/README.md)**，主流程见 **[SKILL.md](pptx-agent/skills/pptx/SKILL.md)**。

## 本地运行

需要 Python 3.11+、LibreOffice 和 Poppler。在仓库目录执行：

```bash
cd pptx-agent
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/pptx --help
```

插件目录包含 `.codex-plugin/plugin.json`、`skills/` 和 `hooks/`；将 `pptx-agent` 作为插件目录使用。安装和 hooks 说明见插件 README。

## 仓库范围

`pptx-agent/` 包含插件、测试和必要资源；`workflow/` 包含持久日志与 Codex app-server 传输；`runner/` 包含隔离的制作执行端；`website/` 是已上线网站的源码快照。历史交互运行时和相关文档保留供旧版本分析，当前单文件工作流不启用它们。用户任务、账号凭证、运行日志和本地配置不上传。

网站支持制作中的聊天、修改意见、附件、暂停、版本下载和断点续做。普通聊天保留已经完成的审核，实际修改使旧审核失效；恢复验证检查点，上传超时核对准确文件哈希和修订号，已审核成品可只重传。运行说明见 [runner/README.md](runner/README.md)。历史逐项进度见 [执行清单](docs/interactive-runtime-plan.md)。

技术说明：[架构](docs/interactive-architecture.md)、[兼容性](docs/interactive-compatibility.md)、[PowerPoint 实测清单](docs/manual-powerpoint-verification.md)。

`blank.pptx` 是创建演示文稿所需的空白资源。导出会进行结构校验和实际渲染；静态渲染不能证明 PowerPoint 中的动画、视频或高级对象播放完全一致。
