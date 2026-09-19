# Rick PPT · PPTX Agent

[![PPTX LAB · 点击进入网站](https://rick-ppt.woodsy-crane-8759.chatgpt.site/og.png)](https://rick-ppt.woodsy-crane-8759.chatgpt.site)

**[进入网站 · 在线制作 PPT →](https://rick-ppt.woodsy-crane-8759.chatgpt.site)**

一个内容优先的 Codex PowerPoint 插件：先调查与阅读，再写逐页内容大纲，制作原生可编辑的 PPTX，最后由独立上下文审核内容和视觉效果。

内容研究按任务需要投入精力，不固定时间或 token 比例。页面形式、字体、图片和分步呈现服从内容与观众需要，不强制套用固定模板。

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

仅包含插件代码、技能参考、必要资源和使用文档。网站服务端、队列执行端、用户任务、测试、评分结果、运行日志和本地配置均不上传。

`blank.pptx` 是创建演示文稿所需的空白资源。导出会进行结构校验和实际渲染；静态渲染不能证明 PowerPoint 中的动画、视频或高级对象播放完全一致。
