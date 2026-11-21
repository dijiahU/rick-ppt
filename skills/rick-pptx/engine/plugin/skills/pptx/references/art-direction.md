# Art direction

<!-- developed-composition/v1 --> <!-- style-context/v1 --> <!-- deck-surface/v3 --> <!-- background-exclusion/v1 -->
<!-- concrete-reference-transfer/v1 --> <!-- visible-explanation/v1 --> <!-- visual-presence/v2 --> <!-- visual-coverage/v1 --> <!-- image-first/v1 -->

Read once before the first page. You own the whole visual sequence: direction,
pages, render checks and repairs. For a small scoped edit keep the existing visual
language and use only what the edit needs.

## First principle: design is for getting the message across

Every visual decision serves one goal: the audience takes in the message quickly and
correctly. Beauty, variety and finish matter because they help attention and
understanding, never for their own sake. A page that looks impressive but makes the
audience search, guess or read everything at once has failed. When rules conflict,
choose what the audience will grasp faster.

Work each page out like a designer before building it. For the cover, every key page
and the closing page, submit this **page design sheet** with `pptx_page_design_context`
using `action=page_plan` (saved on acceptance). Give one short decision per item,
then build from it:

1. **Takeaway.** The one sentence this audience should leave with; it becomes the
   headline (the point, not the topic: "注册转化率升至 4.6%", not "注册数据").
2. **Relationship.** What the content is: who/what (portrait, object), how much (one
   number or a chart), where (map), when (timeline), how (flow), why (cause, comparison).
3. **Steps.** How many things the audience must take in, in order, and where each gets
   its moment: its own page if the count allows, otherwise its own click. One thing
   at a time.
4. **Hero.** The single element that carries the takeaway and its share of the page
   (e.g. "+23, about 40% of the height"). Everything else is visibly secondary.
5. **Reading order.** ① ② ③: what the eye should meet first, second, third. Size,
   contrast, position and click order must agree. Copy this line into the slide notes
   as "阅读顺序：① … ② … ③ …".
6. **Cut.** What you removed because it does not serve the takeaway (keep units,
   qualifiers, sources).
7. **Visual idea.** The one move that makes this page specific to this content and
   memorable, e.g. "+23 is the only figure going against the trend", "one entrance
   followed through all four stages". If the idea would fit any deck, it is not one.
8. **Rejected.** One option you considered and why it reads worse for this audience.

Ordinary pages need only items 1, 2 and 5. Worked examples of the whole sheet, with
the plain version each replaced, are in [worked-examples.md](worked-examples.md):
read them once before page 1.

After the render, check from the audience's seat: glance for three seconds. Can you
say the takeaway? Did the eye follow ① ② ③? If not, the page is not done. Organise
with alignment (one grid, shared edges), contrast (clear primary and secondary,
nothing equal by default), repetition (one system across the deck) and proximity
(related items closer to each other than to anything else; a label touches what it
names; a unit sits on its number's baseline, never over it). A page that keeps three
or more competing elements (a photo, a portrait, a paragraph, a chart) at similar
weight must be split: across pages when the count allows, or into clicks where only
one element holds the main position at each step.

## Deck direction (before page 1)

1. **Name the occasion and its audience, then submit the deck plan.** Who is watching,
   in what setting, and what should they feel and expect to see? A wedding opening is
   for relatives and friends who want to see the couple and feel joy; a club recruitment
   is for new students who want to see people having fun; a weekly report is for a
   manager who wants the exceptions fast. Submit it with `pptx_page_design_context`
   `action=deck_plan` before any page plan; every page's hero and idea serve it.
   Explicit user choices and protected template elements come first.
2. **Look before choosing**: two or three strong examples of this occasion (a real
   wedding opening, a club recruitment poster, a launch keynote) for what its audience
   expects, and two or three works of craft in the same mood (see content.md).
   Register the useful ones as references.
3. **Pick the register** and start from its defaults:

| Register | Typical genres | Defaults |
| --- | --- | --- |
| restrained | weekly and work reports, academic talks, technical reviews | White ground, dark text, one primary plus one accent, clear charts and real pictures |
| standard | lessons, proposals, project reviews, public talks, explainers, training | Light ground with full-colour covers and section pages; colour, pictures and diagrams carry the pages; richer layering than a report |
| expressive | product launches, pitches, brand decks, exhibitions | Brand or subject colour used boldly; full-bleed photography; dark grounds allowed; covers and key pages composed like posters |
| celebratory | weddings, birthdays, annual parties, recruitment, ceremonies, festivals, team events | People at the centre (photos, or clear frames for them, or illustrated people); warm saturated colour the occasion expects (red and gold for a Chinese wedding, bright colour for students); big pictures, layered composition, lively type and decoration with meaning; nothing cold, sparse or office-like |

   Restrained is for reading fast, not a safe default: lessons, events and personal
   stories need richer, more layered pages. Reserve peaks for the messages that need
   emphasis; routine pages may reuse layouts.
4. **Write `deck-style.json`** in the task root (format in scripts/deck_style.py):
   register, named colours (background, text, muted, primary, accent, and positive or
   negative when needed), type sizes, margin, reusable layouts, references and page
   rhythm (peak, working or rest). Check rhythm in the rendered sequence. Use `@primary`, `@text` and so on for new designs in native batches
   and edits. Include retained template colours in the palette used by page checks.
   Record the choice and its reason in `design_direction`.
5. **Reuse graphic devices with a clear job**, such as an accent mark for exceptions or a rule grouping related items. Default type: SimSun for reading text,
   DengXian (等线) light, regular and bold for headings and figures, Arial for Latin
   numerals and labels; weight contrast is now available, use it. Set a type scale of
   three or four steps in deck-style.json "type" and keep to it: a projected page needs
   body text of 18 pt or more and labels of 14 pt or more, and a middle step between a
   giant figure and the small text so the page does not jump from 200 pt to 14 pt;
   units and qualifiers are sized and spaced with their number. If used, record the devices and their jobs in deck-style.json "devices".
6. Avoid both failures. The generic AI look: dark navy, dark green or charcoal full-page
   surfaces on a report; a kicker over every title; tinted cards around everything;
   many shades of one colour; ornament with no job; and the quiet AI look, a warm-white
   page with one object, a thin rule and a lot of empty space, used whatever the
   occasion. The bare page: every element boxed inside the margins from the top left,
   no device, text set flat in one size; tidy, but not designed. Complexity is a skill
   to use: layered pictures, several sizes of type, decoration that carries the
   occasion, a dense but ordered page are often what the audience expects.
7. Test the style on the first real body page. If it does not work, change the file
   now, before it spreads.

## Every page

For a [template base page](content.md), fill the existing slots and check the render
in step 5. Keep the source arrangement and type hierarchy. The three-sketch and
structural rebuild rules apply to newly composed pages. If a base page's structure
fails, choose a template page that fits the relationship better.

1. **Message and main visual.** What should the audience see, understand or compare
   here? When the story is about people (a couple, a team, a club, a customer), the
   people are the subject: use supplied photos, a clearly marked frame "替换为你们的照片"
   sized for one, or illustrated people labelled illustrative; never let an object
   metaphor stand in for them. Choose what carries it and make it big:
   - real places, objects, artworks, documents, products, interfaces: authentic
     images (supplied files, `pptx_open_images`, `image_query`) with native labels;
   - For illustrative scenes, concepts, people or mood, generate when useful and label the image illustrative. For a generated full-bleed plate reserve clear title space, crop to the deck aspect ratio and set text natively. A
     generated full-page mock-up can find a key page's direction; rebuild it as plate
     plus native text. Objects in a set are generated one by one in one style;
   - processes, structures, comparisons: native diagrams showing the real objects and
     the change, not boxes of paragraphs joined by arrows;
   - data: native charts with direct labels and honest scales;
   - words as the subject (a quote, a decision): typography with strong scale contrast;
   - mood, an option in any genre rather than a default: atmosphere or texture
     photography (licensed, or generated and labelled illustrative) for a cover, a
     section opener or a picture-and-text split, when the deck's direction calls for it;
     many decks are better served by graphic devices, data and real subjects alone.
     Choose its feeling for the occasion (a report: morning light, a workspace; a
     wedding: the couple, warmth, celebration; a recruitment: people together) and let
     it keep its own light and colour. Choose picture and layout together: its horizon, diagonal or empty
     area decides where the words go. Take the palette from it (pptx_study_reference
     suggested): a light clean ground of its family, never its dominant mid-tone; a deep
     anchor for type; at most one small accent; distinct lightness steps between ground,
     picture and type;
   - small signposts: one icon set from `pptx_icons`.
2. **Reference.** When composing a cover, key page or closing page, search for that
   page's actual relationship. Start with planning references and the inspiration mode of the
   template library (pptx_reference_library action=inspire with the page's structural job,
   e.g. "一个关键数字加两条说明", "图文叠压 标题跨图"; its best pages come from any genre, so
   a fashion or exhibition page may hold the right composition for a report), then outside
   works when nothing there fits:
   painting, film stills, photography, posters and editorial design, on the subject or
   not; Pinterest (English and Chinese, save_images) and image_query. Ordinary pages reuse
   the references and structures already chosen, without a new search or study. Pick the
   chosen library page with `action=pick`. Study the reference with
   pptx_study_reference (its mass study is the composition under the content) and say
   in your own words where the eye lands first and goes next, how the big shapes
   balance or pull, what is grouped, what is empty and why it works. If the structure
   is hard to name, rebuild it in grey blocks (sketch, a master copy). Borrow the
   structure, never the picture or content; record work, creator, source and what you
   borrowed once in the reference register.
3. **Sketch.** For a newly composed cover, key page or closing page, sketch three
   options in grey blocks, each anchored outside your own habits: A carries over the structure of a
   master of this register, B the structure of a work from another field (a painting,
   photograph or poster), C a concept: first one sentence on the form that carries the
   message (e.g. "+23 is the one figure going against the trend"), then its blocks; a
   concept never invents a quantity (no bar without a real value behind it). The
   three must differ in fundamentals: where the focus sits and how big it is, whether
   there is a title bar at all (a title can be the focus or merge with the message),
   figure and ground. After you estimate how likely a generic AI deck would produce each option
   (the sketch tool takes "anchor" or "concept" and "typicality" for each option and shows each
   anchor's mass study above its sketch), the host draws one of the less typical options to try first (try_first);
   build it unless it cannot carry the message, then take the next in fallback_order. Other pages reuse the
   deck's chosen structures and graphic voice. The focal point is the page's message, not its most
   dramatic fact. Every large empty area has a job (breathing room for the focus,
   separating groups, leading the eye), or it is left over.
4. **Build.** Decide each element's size, position, crop and colour. Size follows
   the takeaway. Label hypotheses and keep supporting details secondary. Hold the craft in every register: decisive scale contrast, one alignment
   grid, labels attached to what they name, qualifiers and units kept, careful
   tracking, leading, line length and Chinese punctuation. For a key picture look at
   pptx_study_reference crops before settling on the whole frame. Plan click reveals
   for multi-step content: entry state, each click group, complete final view.
   Covers, section openers and closing pages, and every page of an expressive or
   celebratory deck, go further: type as image, full-bleed plates, layered pictures,
   bold scale and colour.
5. **Look.** Render. For the cover, key pages and closing page use fresh_eyes
   (blurred, stamp-sized, mirrored: can you point to one focal point?) and compare with
   the reference. Check base pages against their source, including ordinary pages.
   A passing first render can stand. Build each new page in one batch and render;
   fix the biggest problem with batched edits and render once more:
   two renders settle an ordinary page, key pages may take a third. If the intended
   structure is missing (a title too light to hold its side, a split focus, an empty
   field that filled up), fix the biggest problem first and render again. When a newly
   composed key page reads flat, empty or generic in fresh_eyes, return to step 2 with
   a different structural query (inspire, a template page with that arrangement, a picture).
   Sketch again and rebuild the page at most once. Snapshot
   before a big recomposition and revert if it gets worse. Every few pages view the
   rendered sequence and check the planned rhythm.

Native tools: edit_objects adds rotate, vertical, tracking, leading, opacity, gradient
(scrim over a picture), shape (a picture cut to an ellipse or diagonal) and crop.
Connectors in flow diagrams run in aligned horizontal and vertical routes with
consistent strokes; use named native groups for composite objects.

Every new deck needs real pictures on its important pages, not one token image: in a
five-page lesson expect several pages built around an actual artefact, place, map or
scene. Acquire files early so pages are composed around them; embedded assets need
local files and provenance (research-and-assets.md).

## Truth and editability

Never fake real screenshots, photos, results, quotes or data; generated images are
illustrative. Keep text, diagrams, charts and formulas native and editable; raster
images are for real pictures, not whole-slide text.

## Repairs

Fix the region the reviewer identified while keeping successful neighbours, facts and
animation. For weak structure, choose a better-fitting source page for a template base
page. For a newly composed page, return to step 2 and search, sketch and rebuild. Fix
layout details locally. Note which suggestions you applied or kept and why. Never
claim an unapplied change.
