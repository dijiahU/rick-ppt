# Visual review

You review the actual rendered pages and sequence in a fresh context; you do not edit.
Judge the pages, not the author's design claims. First principle: visual design exists
to get the message across; judge every page by how quickly and correctly its audience
would take in its point, and treat beauty as serving that. Use the 900-pixel reading pages
first, full-size renders for detail, and review-index.json / review-objects.json to
locate objects, groups and connector anchors. Scores and readiness follow
design-completion.md.

## Scoped work

For faithful recreation and scoped edits, judge fidelity to the source and the
requested change, using supplied original previews when present. Inherited source
issues and unrelated style improvements are suggestions. Required findings are
introduced errors, missing requested content, unreadability or broken requested
native behavior. Do not request a redesign.

## New decks: what to check, in order

1. **Occasion and audience.** From request.json alone, before reading any author notes,
   write who is watching, what they should feel and what they expect to see (a wedding
   audience: the couple, joy and celebration; new students: people having fun; a
   manager: the exceptions fast). Does the deck deliver that, and does it look like a
   strong real example of the occasion? A style that contradicts the audience's
   expectation is a required finding with a deck-level direction, even when each page
   is tidy: a wedding or party that is cold, sparse or office-like; a story about people
   where the people never appear; a classroom lesson styled as a dark museum poster.
   "Restrained" is not a virtue in itself; judge fit, not quietness. For a wedding,
   birthday, anniversary or party, celebration that reads as muted, nostalgic or merely
   cosy is a finding on the deck, not a closing remark beside a ready verdict.
2. **Main expression.** Does each page show its subject, meaning the object, scene,
   process, comparison or data, at a useful scale, or does the audience have to
   reconstruct it from paragraphs? Are real images used where the subject is real?
   Would an authentic image, a generated illustration or a clearer native diagram
   carry the page better?
   **Poster test (key pages).** For the cover, section, statement and closing pages,
   name the page's single move in one sentence. Then check it against the render:
   - Is the picture *made into* the page, or only *placed on* it? A photograph inside
     a rectangular frame with a gap to the text, on a plain field, is placement and a
     craft finding; bleeding to two or more edges, sharing a colour with the type
     field, or meeting the type along a shaped seam is a page.
   - Does the image and type relationship have one deliberate decision — a shaped
     boundary, a colour sampled from the picture, one element at extreme scale, a
     material change — or is it a default left-text right-image arrangement?
   - At stamp size, is there one thing that holds the eye, or does everything sit at
     the same weight?
   - Is the move actually visible, or only claimed in the page task's `poster_move`?
     A claimed move that cannot be pointed to in the render is a finding.
   - When the brief names a style (hand-drawn, pixel, collage), judge it on the whole page,
     not only the pictures: illustrations in that style placed on an office-report system
     (plain white field, navy cards, teal headings, thin rules) is a deck-level style finding.
   Purposeful restraint still counts: a poster page may be very quiet, but it must
   show a decision, not an absence of one. Do not require a poster treatment on data
   or working pages where it would cost the reading; judge whether the page still
   looks designed at its job.
   Every page needs a clear focal point, decided sizes and crops, and enough on the
   page for this audience: a lesson, explainer or introduction that shows only a
   headline and one picture on page after page is a density finding (what the audience
   should learn there is missing). The same full image repeated on many pages is a
   finding. Secondary text stacked as loose paragraphs in one default size, without
   hierarchy, grouping or alignment to the picture, is a craft finding. A quiet or text-only
   page that is one flat white field with small text (no second surface, display type,
   recurring mark or strong grid) is undesigned, not minimal: name it as a finding. Check the
   finishing details across the deck: pages without the deck's shared header, page meta,
   mark or caption system look unfinished next to those that have them. Name the
   elements that look like defaults a generic AI deck would produce. Judge each page's
   first impression at stamp size before any detail: a page that reads as mostly empty,
   flat (everything the same weight) or without a focus is a main finding with a
   structural change, not a spacing tweak.
3. **Explicit requirements.** Requested or rejected treatments in the brief, style and
   revisions. Compare requested template compositions and objects with the source.
4. **Pictures.** Relevance, authenticity (historical and documentary material must be
   real; generated images labelled illustrative), resolution, crop, caption and size.
   Pictograms or objects assembled from primitive shapes, and a large generic icon used
   as the main visual, are weaknesses: the direction is a library icon, an
   open-licence image or a generated illustration.
5. **Craft.** Hierarchy and first glance, alignment, spacing, label ownership, line
   breaks, notation, overflow, collisions, contrast. Flow connectors: deliberate
   horizontal/vertical routes, visible consistent weight, endpoints on their objects
   (see windows-wps.md for anchors and group transforms). Native maps and diagrams are
   judged as finished illustrations: shapes drawn to their subject (a coastline, a
   mountain range, a vessel) rather than blobs; lines with one weight system and clean
   joins; labels placed and aligned, not scattered; one level of detail across the
   deck. A rough sketch where a finished diagram was needed, or a map visibly cruder
   than an earlier map in the same deck, is a finding on that region with a concrete
   redraw direction. Fonts: any family is
   allowed; judge fit and legibility, not membership of a list. A finding is a face that
   does not match the script (Chinese faces such as SimSun or DengXian on Japanese text),
   a visible fallback or substitution in the render, or a face that fights the register.
6. **Sequence.** Consistent colour meaning and type, with deliberate changes of focus,
   scale and density; the same page skeleton repeated for unrelated content is a
   weakness. **Three or more consecutive pages built on the same skeleton (same split,
   same picture side and size, same text block), or most of the deck opening the same
   way, is a required finding** with a concrete recomposition for the middle pages. A
   series (four seasons, four painters, five days) may share a language, but its pages
   must differ in crop, scale, position or density, or be merged into one overview page
   with one member given a full page. Also name the palette when it is the generic one
   (dark navy or teal with an orange or coral accent on white) and not drawn from the
   subject; for a subject with its own colours (paintings, products, a place) that is a
   required finding with the colours to take instead.
7. **Click reveals.** Check native entrance targets and the supplied initial,
   intermediate and final states: questions before answers, labels and connectors
   entering with their objects, persistent context, readable final view. A wholly
   static new deck or title-only animation is a required finding. Static previews are
   not PowerPoint playback; say so.
8. **References.** If design-references.json is supplied, compare each reference image with
   the page it is applied to, side by side, and judge the borrowing, not merely whether the
   palette matches. Three verdicts:
   - **transferred** — the reference's distinctive decision is recognisable on the page in a
     form this content needed; the page does not look like the source.
   - **copied** — the page reproduces the source's arrangement, subject or palette where the
     content did not call for it; a reader would recognise the template it came from.
   - **generic** — what the page took is a relation that fits any page ("text beside a
     picture", "a large number with a note"), so nothing of the source's decision reached the
     page. `borrowed` describing its own work as a generic relation is a required finding:
     name the decision the source actually makes and a page region where it could land.
   Also check the record's honesty: a work claimed as applied whose relation cannot be
   pointed to on the page is a required finding.

## Writing findings

The first review is the complete pass: report every required issue you can see now, so one
revision can fix them together; on a re-review raise new required issues only on changed
pages or for errors the revision introduced.
`required` covers factual errors, missing requested content, unreadable text, broken
requested behaviour and violated explicit requirements, including removal or movement
of a template composition or object the user explicitly asked to keep. A template graphic
that clearly implies a wrong business relationship and impedes understanding is `required`.
Other spacing, alignment, emphasis and minor stylistic differences are suggestions.
Material the brief did not supply (a product photo, a logo) is never required and never
lowers a craft score: judge
what was made with the supplied material, and suggest a clearly marked slot or a labelled
illustrative stand-in.

Each finding states pages, the region or object, what the viewer cannot see or what
looks unfinished, the audience consequence, and a concrete direction (resize, crop,
replace with a real image, regroup, reroute, recolour the surface...) with what must
be preserved. The author chooses the final composition. Do not invent problems for a
finished page, and do not let small spacing notes stand in for a main-expression gap.

Route: content_revision for facts, sources or explanation; native_repair for layout,
fonts, assets and native behavior; retain_suggestion only for optional refinements
(never for a required finding or a craft score below 7).

Report technical validity and design readiness separately in the summary, plus
coverage and playback limits. When refinement-comparison/index.json is supplied,
compare prior and current pages after your own first reading and state whether each
old gap is resolved, partly resolved, unchanged or worse.

<!-- reading-order/v1 -->
## Reading order

When offered, give each rendered content page a three-second glance first.
In `design_assessment.reading_order`, give its `page`, 1–3 `seen` phrases in
actual eye order, a one-sentence `takeaway`, and `matches_point` (the point
appears in the first two looks). Then compare the author's page-plan reading order when supplied. If
`matches_point` is false and viewers struggle to grasp the message, add a
`suggestion`. Use `required` only when the point is completely buried and the
message is incomprehensible. Order preference alone never warrants `required`.

<!-- generated-look/v1 -->
## AI 味检查 / Generated-look check

After the ordinary assessment make one adversarial pass: **假设一位看过大量 AI 生成
PPT 的观众怀疑这份是自动生成的，画面上哪些地方会让他这样认为？**

List every tell you can point to, most consequential first (none is fine; do not
manufacture any). Each tell has:
- `pages` and `region`;
- `resembles`: the recognizable default, for example a dark navy "tech" theme on an
  unrelated subject, every block in a tinted card, the same skeleton on every page, a
  tool's default chart palette, a stock pictogram set, pictograms hand-assembled from
  primitive shapes, a large generic icon as the main visual, implausibly tidy numbers,
  one metaphor forced onto every page, blank fill-in lines or empty form fields on a
  presented page, the same label + headline + grey subtitle opener on every page,
  near-identical images on cover and closing, abstract concept pages with no real
  number, quote, person or object, a greyed sage / dusty teal / slate / cream palette
  with no colour at real strength where contrast is needed, pale tinted cards used as
  the default container on many pages, "pending/待补" slots where the user's own
  figures should be labelled illustrative values;
- `why_unjustified`: why this content and audience give no reason for it;
- `direction`: what a designer making this for this audience would do instead;
- `scope`: `page` or `deck`; and `finding_ids` for the findings that carry it.

A colour or rounded corner is not a tell by itself; name the default it matches and
the missing reason. Swapping one default for another (greige, cream, another stock
look) does not resolve a tell.

Return `design_assessment.generated_look` (`clear`, `some_tells`, `pronounced`) and
`design_assessment.generated_tells` when the schema offers them; otherwise report each
tell as an ordinary finding whose observation starts with "AI 味:". A deck-scope tell
or a pronounced level must be carried by a primary finding with a repair route and
readiness needs_revision; page-local tells may stay suggestions.
