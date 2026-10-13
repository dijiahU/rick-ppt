# Actual fonts

Use `font-catalog.json` and `fonts/index.json` to choose from real installed files.
For a new deck, select Chinese and Latin typography together for the content,
audience and chosen expression. Start with Noto Sans CJK SC + Inter for clear
mixed-language explanations, Noto Serif CJK SC + Source Serif 4 for an editorial
voice, or Noto Sans CJK SC + Source Sans 3 for longer explanatory text. These are
options, not a fixed rotation. Preserve supplied template fonts for scoped edits.
Use meaningful hierarchy, space and real weights; do not indiscriminately bold
Chinese, use a serif for tiny labels, or change font families page by page.
For a gentler title weight, `noto-sans-sc-medium` and `inter-semibold` are also
available on demand; use their actual returned family names instead of simulated
bold. Contrast title/body primarily with purposeful scale, placement and spacing.

The starter regular/bold sans files are already in `fonts/`. A missing resource
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
python PLUGIN/skills/pptx/scripts/font_assets.py --root . check --ids noto-sans-sc-regular inter-regular --text '中文 English 2026，公式 α + β'
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
--root . theme --workspace WORKSPACE --latin Inter --east-asian 'Noto Sans CJK SC'`.
This changes native major/minor font schemes. Preserve the original theme during
scoped edits unless the user asked to change it; explicit run fonts still take precedence.

Fonts are installed inside the task, not globally by public jobs. Downloading
does not embed fonts into a PPTX or install them on the recipient's machine.
Do not claim portability or PowerPoint playback from a LibreOffice preview.

## Standalone skill

When no font broker is exposed, use `python SKILL_ROOT/scripts/font_assets.py --root TASK_DIR ensure inter-regular noto-sans-sc-regular`. This downloads actual official catalog files and OFL licenses into the task, producing the same metadata/coverage checks. For a locally authorized Mac installation add `--user-install`; keep user installations out of public job flows. A Linux local render can use `FONTCONFIG_FILE=TASK_DIR/fonts.conf`. Mac native apps need the fonts installed in the user font directory. Honor supplied-only/offline briefs; report unavailable resources rather than silently substituting.
