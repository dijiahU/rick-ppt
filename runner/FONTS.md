# Fonts

Default for new work: **Times New Roman** for English/Latin and **SimSun (宋体)** for
Chinese (IDs `times-new-roman-regular|bold|italic|bold-italic`, `simsun-regular`).
A secondary family for headings, figures and display text is also prepared:
**DengXian (等线)** light/regular/bold (`dengxian-light|regular|bold`) and **Arial**
(`arial-regular|bold`); both ship with Windows 10+, Office and WPS.

Also approved (installed by default on Windows and bundled with Office for Mac), installed
into the task only when you use them: `python font-proxy.py ID --text '...'`.
Chinese: Microsoft YaHei 微软雅黑 (`microsoft-yahei-light|regular|bold`, the clearest
weight range for reports and modern decks), SimHei 黑体 (`simhei-regular`), KaiTi 楷体
(`kaiti-regular`) and FangSong 仿宋 (`fangsong-regular`) for lessons, classical or literary
text. Latin: `calibri-`, `cambria-`, `georgia-`, `century-gothic-`, `verdana-`,
`tahoma-` + `regular|bold`. Never use fonts outside these lists (PingFang, Source Han,
FZ/HY families...): Windows substitutes them and line breaks, boxes and arrows shift.
Explicit user fonts
and supplied template typefaces take precedence. The real files
are in `fonts/` with `fonts/index.json`; never rename a substitute as SimSun. SimSun
has no bold face, so build hierarchy with size, spacing and the Latin weights.

Set the theme of a new deck to the pair so inherited text matches:

```
python PLUGIN/skills/pptx/scripts/font_assets.py --root . theme --workspace WORKSPACE --latin 'Times New Roman' --east-asian SimSun
```

Check coverage of actual text:

```
python PLUGIN/skills/pptx/scripts/font_assets.py --root . check --ids simsun-regular times-new-roman-regular --text '中文 English 2026'
```

Use the returned files for native_canvas measurement (`--font` Chinese face,
`--latin-font` Latin face). An extra OFL font for a real need can be fetched with
`python font-proxy.py FONT_ID --text '...'` or `--url HTTPS_TTF --license-url URL
--family 'Name'`; downloading does not embed it in the PPTX. LibreOffice previews do
not prove PowerPoint/WPS rendering.
