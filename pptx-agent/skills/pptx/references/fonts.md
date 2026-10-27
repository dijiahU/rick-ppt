# Actual fonts

Use `font-catalog.json` and `fonts/index.json` to choose from real installed files.
For new work, Rick's default is **Times New Roman for English/Latin** and
**SimSun (宋体) for Chinese**. Apply the pair to native runs, theme defaults,
chart/table labels and inherited text. Preserve explicit user font choices and
actual supplied template typefaces for scoped edits. Newly recreated image text
without a specified source typeface still uses the defaults. Descriptions such as
"rounded", "handwritten" or "looks like" a font are uncertain visual observations,
not an explicit font requirement or verified template font metadata; do not use
them to justify a decorative replacement. Read [Windows WPS compatibility](windows-wps.md).
Use size, spacing, hierarchy and real weights rather than acquiring more families.
The default IDs are `times-new-roman-regular`, `times-new-roman-bold`,
`times-new-roman-italic`, `times-new-roman-bold-italic`, and `simsun-regular`.
Use actual returned family/style names; do not simulate an unavailable SimSun bold.
Special fonts are exceptions for an explicit requirement or functional need.
For a functional exception, identify the concrete need and record the actual
family/style/weight, relevant glyph forms and coverage, plus recipient availability
or verified editable embedding before using it. An appearance guess alone is not
that evidence. A downloaded font is not embedded.

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
