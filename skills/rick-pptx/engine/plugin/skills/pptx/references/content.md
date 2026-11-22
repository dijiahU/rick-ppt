# Research and page content

<!-- research-breadth/v1 --> <!-- design-task/v1 -->

Work out what the audience should understand, do, judge or feel, within the brief,
page count and source scope.

## Research

- Search the question, not just the topic name: origin, mechanism, conditions, a
  concrete case, consequences, competing views. Look beyond the first official page
  for real uses, outputs, first-hand experience, debates and visual material.
- Search three kinds of thing together: facts, real cases or material that can appear
  on a slide (photos, figures, documents, outputs), and finished visual work for this
  kind of audience. For each planned page ask which picture people in the field use
  for it (the mural, map or artefact a textbook or museum shows for that event, a
  product's real screen, the photo from the report) and look for that one by name. Use Chinese and English queries and batch independent searches.
- Built-in web search is the main channel: one call can carry many `search_query` and
  `image_query` entries and returns in seconds. `pptx_browse` reads a logged-in page in a
  few seconds for what built-in search cannot reach: Pinterest for finished visual work: slide layouts and
  the art style of the subject itself. Search in English and Chinese ("silk road
  illustration" and "丝绸之路 插画"); English results are usually much stronger. Pass
  save_images to keep full-size pins and register the best as references. They are other
  people's work, so bring them into the deck in one of two ways: open the pin and use
  its original only when the source is public domain or openly licensed (museum,
  Wikimedia); otherwise describe what makes it work (medium, palette, line, motifs,
  composition) and give that description to pptx_generate_image for an original
  illustration in the same direction, then compare the result with the pin. Use the identifying
  terms of the subject once known. Open a promising specific case before dropping it.
  Do not retry login/captcha walls.
- Two kinds of example, for two jobs. Occasion examples show what this audience
  expects (what is covered, the mood, who appears): the template library, image_query
  and Pinterest for the occasion itself ("婚礼开场 视频 截图", "社团招新 海报",
  "product launch keynote"), bestpitchdeck.com for pitches. The craft comes from strong
  work in the same mood, found on Pinterest and image_query in English and Chinese:
  wedding invitations and wedding films, festival and concert posters, children's
  picture books, campus and event posters, editorial magazines, film posters, brand
  campaigns, FT and Economist graphics for data. Match the mood to the occasion; do not
  default to minimalist masters. For quiet and text-only pages in any register, the
  craft references are Swiss / International Typographic Style posters, Kenya Hara and
  MUJI, Penguin book covers, book interior spreads and the template library's best
  restrained decks (action=templates with "极简 杂志 黑白"): look at how they use a
  second surface, display type and a recurring mark. Search by name and work; style words alone mostly
  return template sellers' mock-ups. pptx_browse saves each screenshot under
  references/browse/; register the useful ones as local_image references.
- Compare whole templates while planning. Start with the user-supplied template, then
  rank local candidates with `pptx_reference_library` `action=templates`. Open the
  high-ranked candidates that fit the setting with `action=deck` and compare all their
  pages for coverage of key relationships and usable slots. Record one line per key
  page in the decision-plan reference application or source-notes.md using
  `page id | source page id (or —) | base / structure / new`. Mark `new` for
  master-only pages and whenever no template page expresses the key relationship.
- Choose among three template uses:
  - **Base page (`base`).** When a template page fits the message, relationship and
    slots, keep the original page. For a library base, fetch the editable deck with
    `action=template` and unpack it. Use `template_map` for slots and `template_select`
    to retain pages in order (pages may repeat). Replace sample text with `edit_objects`
    and refill picture frames with `template_image`. Keep positions and visual hierarchy.
    Pictures carry much of a template's finish: refill each frame with a relevant
    picture instead of deleting it, and replace every sample text. When content needs
    another arrangement, take a template page that has it instead of moving objects.
    A passing first render needs no sketches. On a large-type cover or closing page,
    keep the original display size and hierarchy. Move excess copy into the subtitle
    slot. If a picture frame must become data or a diagram, name the frame and reason
    in `template_preservation`.
  - **Master-only page (`new`).** When only the template's visual system fits,
    keep the template masters, colours and fonts. Add a page using a layout in the
    active package and build its content natively.
  - **Borrow structure (`structure`).** When a useful composition fits the
    relationship and the original page is unsuitable as a base, use `action=inspire`
    for the page's job, then `action=pick` to save the reference. Study it with
    `pptx_study_reference`, then sketch and build the page natively.
- Before reusing a template diagram, write what shape, overlap, direction and grey
  values each mean. Reuse it only when each meaning matches the content.
- The deck's main change or finding is always shown (a step diagram, a before/after),
  even when no template page has it: build that page.
- Prefer building on a template: starting from a well-made template is faster and
  usually finer than starting blank. A template whose style is not ideal can still
  supply the masters, type and a few base pages while you build the rest; replace
  colours, pictures and sample content freely. Leave the library only when the user
  asks for no template, supplies their own, or its look contradicts a stated style or
  brand; record the template used, or that reason, in the decision plan.
- Follow a good case far enough to explain it: starting problem, key actions, result,
  limits. Prefer primary evidence for facts; several reposts of one source are not
  independent confirmation.
- Stop when the outline is well supported and more searching adds little. Later gaps
  can be researched while authoring.
- Note channels, queries, useful findings and dead ends briefly in source-notes.md.

Starting points by subject (leads, not a template): teaching (prerequisites, hard
steps, misconceptions, worked examples); history and people (original sources, the
situation, choices and consequences; separate fact from interpretation); products
(capabilities, real workflows, outputs, costs and failures); places and proposals
(site conditions, users, movement, precedents); reports and plans (observations,
causes, alternatives, decisions).

## Thin briefs

When the brief is one line (introduce a painting, a person, a product, a concept),
research first lists what an informed presenter would be expected to cover: the
best-known facts, the creator's own words or view, how it was made, reception and
afterlife, a well-known debate or recent finding, and one surprising detail. Decide
which page carries each; a finding that only reaches the source notes is lost to the
audience.

When the brief supplies only bare facts (a weekly report, a short list of results),
the deck still needs substance: add analysis, implications, risks and next steps that
follow from the facts, clearly labelled as suggestions. Never invent research facts,
quotes, screenshots or results attributed to real people, studies or companies.

**When the user's own figures are missing, fill them with labelled illustrative values.**
A pitch without a raise amount, a price, traction or a team, a plan without a budget,
a report without the user's own numbers: do not leave "pending" or empty slots (a page
of "待补" reads unfinished). Write a plausible, internally consistent value that fits
the rest of the deck (for example "种子轮 300 万元，用于 18 个月" or "$49 per location per
month") and label it on the same page in small text: "示例数字，非真实数据，请替换" /
"Illustrative figure — replace with actual". For people, use a role and an obviously
fictional placeholder ("创始人 A · 前连锁餐饮运营总监") rather than a real-sounding name.
Keep every external fact (market sizes, studies, competitors) real and sourced; only the
user's own figures may be illustrative. Say in the speaker notes which figures to replace.

## Plan the pages

For each page decide the one point, the evidence and what the audience will see.
Write consequential page tasks as fenced `pptx-handoff` objects in source-notes.md
(format in page-design.md):

- `question`: what the audience should get from the page;
- `evidence` / `materials`: the real support, with file and viewing status;
- `preserve`: conditions, units and qualifiers that must survive;
- `uncertainties`: missing support;
- `visual_opportunity`: the subject shown, the relationship made visible and what
  the audience can point to afterwards, e.g. "each metric tied to where it is measured
  on the bench", not "two-column table". This is the brief for the page, not its
  layout. Choose compositions for new pages while authoring, after the page-level search.

Plan visuals by relationship (art-direction.md). Use authentic images for real subjects, labeled generated illustrations for concepts, and editable diagrams and charts for relationships and data. Keep one detailed copy per evidence passage with an exact locator. Simple pages need only a summary.

Check the sequence before committing: does each page follow from what came before,
add something, and answer the question the last page raised? If an entry could be
pasted onto an unrelated topic, make it specific.

For a scoped edit, record only the requested change and what must be preserved.

## outline.json

title, purpose, optional style, and ordered slides. Each slide has a stable id,
title, substantive reader-facing summary (including a short note on the planned
visual) and optional section. Array order is presentation order; keep IDs stable on
reorder. Detail stays in source-notes.md. Preserve periods, units, denominators and
qualifiers, and check the arithmetic of examples.
