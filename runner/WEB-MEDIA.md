# Network media is available

Select the asset route in decision-plan.json using the plugin's
references/workflow-branches.md: none, supplied, web_import, generate or
source_grounded_native. Execute its acquisition/inspection/embedding and failure
actions. File routes record kind/status/file/origin; completed assets must be used
on their planned page. There is no implicit search, generation or card fallback.

Use this task-local broker for actual public media URLs discovered through web
search, official pages, public asset libraries or supplied references:

```
python web-media-proxy.py 'https://public.example/asset.gif' --source-page 'https://public.example/source' --purpose 'Show the actual ability being explained'
```

Use the task's configured Python interpreter. Wait for the result, inspect the
returned local file and `assets/web-index.json`, then embed it. Search results
are not downloaded files. A page URL is not a media URL. Prefer official/source
assets for identifiable games, films, products, characters and objects; do not
substitute invented artwork merely because it is easier to obtain. Use generated
imagery for an actual original-illustration need, not as a counterfeit screenshot.

The host uses its configured local HTTP proxy when available. Public addresses
and every redirect are checked; the proxy CONNECT target is pinned to the
verified IP and TLS still verifies the original hostname. Task code cannot
select a proxy or change network permissions. Without a local proxy the host
uses direct transport. Downloads have a shared 65-second budget, including
redirects, and at most one retry per transfer for an empty transient failure.
HTTPS DNS uses one bounded retry within its existing time budget and briefly
caches only verified public answers within their TTL (at most 60 seconds), so
multiple images from one source do not repeatedly depend on a fresh resolver call.

On failure read `error_code` and `details`: DNS, connection, TLS, HTTP status,
size and non-media responses are distinct. Do not keep swapping URLs or
repeating a request for the same transport problem. The host already performs
the bounded transient retry. A page/404/non-media response needs a verified
direct-file URL; a size or partial-download failure needs an appropriate smaller
source. Record a DNS/proxy/TLS outage and follow the selected asset branch's
alternative or unmet-requirement action without inventing documentary evidence.

For original concept imagery, use the exposed built-in generator with
imagegen-skill.md when that fits the task; it does not require a failed search first.
Inspect the scoped file in assets/index.json and distinguish illustration from
real-product/case evidence. Keep factual analytical diagrams editable. If an asset
or tool fails, record the observed limitation and reconsider the representation;
no paid API fallback or personal-directory access. Record selected file, provenance
and page/role in source-notes.md. No image quota or fixed composition.

Support is by decoded content, not URL extension:

- PNG/JPEG/WebP/AVIF/BMP/TIFF become PNG; SVG has a disclosed raster fallback.
- Animated GIF retains its original animation and has a separate static poster.
  Embed the GIF, not its poster, when motion is requested.
- Common MP4/MOV/WebM/MKV/AVI media are decoded and converted to H.264/AAC MP4.
- Common MP3/WAV/AAC/M4A/OGG/FLAC audio are converted to MP3.
- Unsupported codecs, active SVG, playlists, executables, documents disguised
  as media and animated non-GIF images that cannot be preserved are rejected.

Only public HTTPS direct files: no sign-in, cookies, DRM, paywalls, private IPs,
shell networking, credentials or permission changes. Respect reuse conditions
and record source page, author/credit and usage context in source-notes.md and
slide notes. The broker validates files, not copyright permission or factual fit.
If blocked or unavailable, explain the exact unmet requirement; do not pretend
an imagined character/item is a verified original. Do not infer every slide
needs media or reuse a random image merely to fill space.

Current public-test resource limits: 30 MB per download, 16 successful imports
and 60 MB normalized assets per task, videos/audio up to 120 seconds, GIF up to
600 frames, images up to 16 megapixels. Final website PPTX remains limited to
30 MB; select appropriate clips and disclose constraints, never silently cut
the source or bypass limits. Import can take several minutes for conversion.

## Native embedding

Keep editable text and shapes. For images/GIF use ordinary native p:pic objects.
For video/audio use embedded media under ppt/media with poster/icon, video/audio
and p14:media relationships, not external URLs. The optional helper follows
Microsoft's Open XML embedding pattern:

```
python media-embed.py WORKSPACE_DIR 3 assets/web-ID-media.mp4 --poster assets/web-ID-poster.png --box 1 1 10 5.625
```

WORKSPACE_DIR is the unpacked OOXML directory. Coordinates are inches. For a
picture/GIF omit --poster. Audio requires a supplied task-local PNG icon/cover.
The default --fit contain preserves aspect ratio inside the box; --fit cover
uses native image cropping, and --fit stretch is an explicit opt-in. Do not
distort a screenshot or character to fill space. Video playback crop behavior
still needs PowerPoint verification; prefer contain for video.
Snapshot first; then validate/render/export using the PPTX CLI. The helper is a
small object insertion utility, not a new authoring route or an export shortcut.
Set crop/aspect ratio and any desired timing consciously through native OOXML.

Browser previews and LibreOffice renders show static posters, not playback.
Downloaded bytes, converted stream validation, PPTX embedding and actual
PowerPoint playback are distinct checks. Report playback as unverified unless
it was actually tested. Do not discard GIF/video just because a static preview
cannot play it. Do not claim native motion paths or Morph from media import.

References:
https://learn.microsoft.com/en-us/office/open-xml/presentation/how-to-add-a-video-to-a-slide-in-a-presentation
https://learn.microsoft.com/en-us/office/open-xml/presentation/how-to-add-an-audio-to-a-slide-in-a-presentation
