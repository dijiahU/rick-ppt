# Research, visual references and assets

Factual research follows content.md. Never put private attachments or credentials
into a public query; respect supplied-only/offline scope.

## Design references

For new decks, look at real finished work that solves the same visual problem: good
examples of this genre (real lessons, reports, pitches), editorial and information
design, photography, scientific illustration, film, posters. Open the actual image;
a title or description is not enough. Borrow concrete decisions and record them once
in the reference register (workflow-branches.md). A reference used only for
inspiration need not appear in the deck; embedding needs its own permission.
When both composition and the main pictured action are unresolved, look for useful
approaches to each. A single work may help both. Two works can contribute separate
decisions, such as a reading path and an annotation method, if their combination
leaves the page easy to read. Judge inspected works by what the audience needs to see
or compare and respect supplied-only reference scope.

Useful starting points when a specific question comes up: W3C Requirements for
Chinese Text Layout (CJK typography); Lupton & Phillips, *Graphic Design: The New
Basics* (scale, figure/ground, grid); Albers, *Interaction of Color*; Wilke,
*Fundamentals of Data Visualization*; Tufte; Mayer, *Multimedia Learning* and Alley's
assertion-evidence slides (teaching); Duarte, *Resonate* and *Slidedocs*; Frankel,
MIT *Making Science and Engineering Pictures*; museum collections (MoMA, Met, Cooper
Hewitt) and designers' portfolios.

## Image and icon routes

Pick the route from what the page must show. Record each kept asset's source,
creator, licence and page role in source-notes.md.

| Need | Route |
| --- | --- |
| Real place, artefact, artwork, map, specimen, historical figure | `pptx_open_images`: openverse (Creative Commons photos from Flickr, Wikimedia and museums) first, then wikimedia, met, artic. Candidates carry licence, pixel size, source page, media URL and a preview sheet. Import with web-media-proxy.py. |
| Any other picture on the web (museum and press photos, product shots) | Built-in `image_query`: returns source page and direct image URL in seconds. Check the source page for rights, then import. The browser tool is only for logged-in platforms; its screenshots are references, not assets. |
| Concept, scene, atmosphere, cover, illustrative people, a product idea with no real image | Built-in image generation, labelled illustrative. A normal first choice when the brief has no imagery. Ask for the deck palette and room for editable text. |
| Small signposts: categories, steps, roles, metrics | `pptx_icons`: one consistent set as native vectors, placed with `add_icon` / batch op `icon` in the deck palette. |
| Exact relationships, data, states to animate | Native drawing and charts. |

Pictograms come from the icon library, not from primitive shapes. Icons label and
organise; the page's main visual is the real subject, an illustration or the
relationship itself.

## Rules for real material

- Historical and documentary people, events and objects need authentic images; real
  app screens, case photos and results are never generated. Generated images are
  illustrative.
- **The user's own things are never generated** as if they were real: their products,
  shop, premises, staff, team, customers and events. A generated picture of "our
  signature sweet" or "our two bakers" misrepresents them, even when labelled. Use a
  photo the user supplied; otherwise place a clearly designed placeholder frame of the
  right size and crop, captioned with what belongs there ("替换为实拍：招牌商品「白川」
  俯拍，深色器皿"), and list these placeholders in the completion summary. Generic
  context (an ingredient, a landscape, a mood, a street) may still be sourced or generated.

## Pictures that look real

A generic real-world scene (hands kneading dough, a bakery counter, a classroom, a
mountain path) is easiest to make convincing with a real photograph: search open
collections first (Wikimedia Commons, Openverse, museum and agency archives, image_query).
When you generate one:

- Write the prompt as a documentary photograph, not an advert: candid moment, available
  or mixed light, ordinary people turned away or partly cropped, working clutter, wear,
  flour on the apron, an imperfect crop, film grain. Avoid "warm", "cinematic",
  "beautiful", "golden hour", "professional", "stock": they produce the generated look.
- Prefer hands, tools, materials and details to faces; faces and smiles give generation
  away first. Keep landmarks and local symbols out unless they are the subject.
- Check every generated photographic picture with `pptx_study_reference` asset_check
  `realism: true` before placing it; a "some_tells" or "obviously_generated" verdict means
  regenerate with its fix, use a real photograph, or switch to an openly illustrative
  style (watercolour, ink, linocut, collage), which does not pretend to be a photograph and
  so never looks fake.
- For an image carrying the explanation, name the detail before acquisition: an
  action and its point of contact, a difference in height, a readable label, or a
  visible before/after change. Specify the viewpoint when commissioning a permitted
  illustration. Inspect the acquired file at the intended reading size and crop and
  point to the detail it actually shows. If it is missing, try another vantage point,
  a better crop, a different asset or a native diagram. Check the annotation endpoint
  and evidence together on the page render.
- Record creator, source page, file URL, licence and required attribution. Do not
  remove watermarks or bypass access controls.
- On a failed download read the actual error and use another legitimate source.

## Technical

Search and generation are host tools, separate from shell networking; only
web-media-proxy.py imports files into the task. For embedding see images.md and
relationships.md; charts in charts.md; reveals in animations.md. Static renders do
not prove animation or video playback.
