# Actual fonts

**Font choice is open (2026-11-26).** Choose the families that suit the language, the
register and any requested style; there is no approved list. The defaults below are a
starting point when the deck gives no reason to choose otherwise. Recipients without a
chosen font are told by the website to install it, so do not avoid a good font merely
because it may be missing on some machines. List every family you used (Latin and East
Asian) in the completion summary.

- **Match the script.** Japanese text uses a Japanese face (Yu Mincho / Yu Gothic,
  Hiragino Mincho ProN / Hiragino Sans, Meiryo, BIZ UD…); Chinese faces render kanji in
  Chinese forms and kana poorly. Korean uses a Korean face. Set run `lang` to the text's
  language (`ja-JP`, `ko-KR`, `zh-CN`…). Chinese text keeps a Chinese face.
- **Match the style.** A hand-drawn journal can take a handwriting or brush face for
  notes; a pixel deck a bitmap display face; an editorial deck a strong serif display.
  Keep reading text legible; use one or two families plus one display face.
- **Install the actual file into the task** so measurements, previews and reviews show
  the real font: any font installed on this host by family name
  (`python font-proxy.py host --family 'Hiragino Mincho ProN' --style W3 --text '…'`),
  or an OFL download as below. Windows names such as Yu Mincho, Yu Gothic, Meiryo and
  MS Mincho are mapped to their macOS equivalents in previews.
- Defaults when nothing argues otherwise: Times New Roman for Latin and SimSun (宋体)
  for Chinese reading text, DengXian 等线 / Arial for headings and figures (Linux host:
  DejaVu Serif and Noto Serif CJK SC). Preserve explicit user font choices and supplied
  template typefaces in scoped edits.

The host prepares genuine installed default faces in `fonts/` when available,
including the actual SimSun face extracted from its collection. Check the manifest;
never rename Songti SC/Noto as SimSun or silently rely on fallback. Host-installed
faces carry source hashes, original licensing metadata and a provenance record;
they are not OFL downloads or evidence that fonts were embedded into the PPTX.
A missing optional OFL resource
can be downloaded without asking the user again, unless the brief prohibits
network access. Author shell networking remains disabled; the host does it:

```
python font-proxy.py noto-serif-sc-regular --text '本页实际中文内容'
python font-proxy.py source-serif-regular --text 'The actual English sentence'
```

For another OFL font, give an official direct TTF/OTF URL, its actual license file
and expected family; do not use a download page, WOFF or an installer:

```
python font-proxy.py custom-font --url HTTPS_FONT_URL --license-url HTTPS_OFL_URL --family 'Actual Family'
```

Read the reply and `fonts/index.json`: actual family/style/weight, task-relative
font file, missing characters, source and license hashes are recorded. A missing
character is not proof of successful fallback. Check the exact current title,
body, numbers and punctuation across the chosen pair with:

```
python PLUGIN/skills/pptx/scripts/font_assets.py --root . check --ids simsun-regular times-new-roman-regular --text '中文 English 2026，公式 α + β'
```

Use the returned files for native_canvas measurements. For mixed text, its
`--font` is the Chinese face and `--latin-font` is the Latin face. Keep them as
editable native runs and set actual East Asian/Latin family names. The host mounts
checksum-verified copies of these same files into the isolated renderer, and logs
their hashes and resolved family names. Inspect actual exported renders for
weight, punctuation, wrapping and substitutions; font inventory is not an
aesthetic verdict. Do not overwrite originals or restyle unrelated template pages.
For a new deck, set its existing theme to the selected installed pair so inherited
text also has intentional typography: `python PLUGIN/skills/pptx/scripts/font_assets.py
--root . theme --workspace WORKSPACE --latin 'Times New Roman' --east-asian SimSun`.
This changes native major/minor font schemes. Preserve the original theme during
scoped edits unless the user asked to change it; explicit run fonts still take precedence.

For a whole-page font substitution, retain versioned before/after renders and the
actual source reference. Compare them at the normal reading scale during existing
authoring and visual review: inspect the changed labels, glyphs, weight, wrapping,
spacing and source fidelity. A different family name or a successful font inventory
does not establish an improvement. If the change regresses the page, retain or
restore the compliant earlier frozen candidate, or repair with the standard pair;
preserve the attempted version. Review changed bytes through the existing bounded
repair route, without a new review stage, content rewrite or imposed design style.
Report unavailable comparison evidence honestly rather than claim it was checked.

Fonts are installed inside the task, not globally by public jobs. Downloading
does not embed fonts into a PPTX or install them on the recipient's machine.
Do not claim portability or PowerPoint playback from a LibreOffice preview.

## Standalone skill

When no font broker is exposed, use `python SKILL_ROOT/scripts/font_assets.py --root TASK_DIR ensure times-new-roman-regular simsun-regular`. This uses genuine already-installed host faces, with source hashes and licensing provenance; it does not download proprietary font files. Missing default faces are reported, not replaced. The existing OFL catalog/downloader remains available for justified alternatives. For an authorized OFL user installation add `--user-install`; keep user installations out of public job flows. A Linux local render can use `FONTCONFIG_FILE=TASK_DIR/fonts.conf`. Mac native apps need the fonts available to that application. Honor supplied-only/offline briefs and scoped templates.
