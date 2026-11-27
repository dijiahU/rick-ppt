# Fonts

**Font choice is open.** Choose families for the language, register and requested style;
there is no approved list. Recipients missing a font are told to install it. List every
family used in your completion summary. Details: references/fonts.md.

- Japanese text: a Japanese face (Yu Mincho / Yu Gothic, Hiragino Mincho ProN / Hiragino
  Sans, Meiryo, BIZ UD…), never SimSun/DengXian; set run lang `ja-JP`. Korean: a Korean face.
- A requested style can carry into type: handwriting or brush faces for a sketchbook,
  bitmap faces for pixel art, a strong serif display for editorial work.
- Prepared defaults: **Times New Roman** (`times-new-roman-regular|bold|italic|bold-italic`)
  and **SimSun 宋体** (`simsun-regular`) for reading text; **DengXian 等线**
  (`dengxian-light|regular|bold`) and **Arial** (`arial-regular|bold`) for display text.
  Also prepared on use: `microsoft-yahei-light|regular|bold`, `simhei-regular`,
  `kaiti-regular`, `fangsong-regular`, `calibri-`, `cambria-`, `georgia-`, `century-gothic-`,
  `verdana-`, `tahoma-` + `regular|bold`.
- **Any other font installed on this host**, by family name, so previews and reviews show
  it (Windows names such as Yu Mincho, Meiryo, MS Mincho map to macOS faces in previews):

```
python font-proxy.py host --family 'Hiragino Mincho ProN' --style W3 --text '実際の本文'
python font-proxy.py host --family 'Klee' --text 'actual text'
```

- An OFL font from the web: `python font-proxy.py FONT_ID --text '...'` or
  `--url HTTPS_TTF --license-url URL --family 'Name'`. Downloading does not embed it.

Set the theme of a new deck to your pair so inherited text matches:

```
python PLUGIN/skills/pptx/scripts/font_assets.py --root . theme --workspace WORKSPACE --latin 'Times New Roman' --east-asian SimSun
```

Check coverage of actual text and use the returned files for native_canvas measurement
(`--font` East Asian face, `--latin-font` Latin face):

```
python PLUGIN/skills/pptx/scripts/font_assets.py --root . check --ids simsun-regular times-new-roman-regular --text '中文 English 2026'
```

SimSun has no bold face; build hierarchy with size, spacing and another family's weights.
LibreOffice previews do not prove PowerPoint/WPS rendering.
