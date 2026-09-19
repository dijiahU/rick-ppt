# Scene rendering and interaction semantics

The browser runtime renders SVG vectors and HTML controls from scene JSON. The
core does not rewrite chart or teaching topic code into React. See the executable
scenes in `examples/controls.scene.json`, `examples/charts-map.scene.json`, and
`examples/primitives.scene.json`. Their SVG, WAV and VP8 assets are local, synthetic
engineering fixtures. Browser playback evidence is separate from PowerPoint
Content Add-in playback evidence.

## Coordinates, events and behaviors

- `event.x/y` are logical scene coordinates after the SVG viewport's letterbox
  transform. `localX/localY` use the current node's inverse screen matrix.
  `parentX/parentY` use its parent's matrix. Rotation and nested scaling are
  included in both transforms.
- Drag and pan change state positions in parent units. Resize and brush use node
  units; scrub maps the target's local extent to `min..max`. Behaviors accept
  axis locks, constraints and bounds. `snap` is either a positive number or an
  object with positive `x`, `y`, `width`, and `height` grid sizes.
- Pointer gestures have pointer and instance identities and use capture, so a
  gesture keeps working when the pointer leaves its geometry. Native controls
  retain their native focus, keyboard and pointer mechanics.
- Events bubble once through the authored node/component/group ancestry, then
  reach `scene`. `target` is the current DSL node ID; `sourceTarget` is the fully
  qualified originating node ID; `child` is its local ID. `instanceId` identifies
  the current repeated/component instance. `locals` are scoped to that receiver.
  Component events retain the originating primitive's value.
- Built-in components attach useful `event.value` data: chart index/series/value,
  matrix row/column/value, table row/column/key/value, GeoJSON feature ID/index/
  layer/properties, or the selected tab/step index. Changes are still expressed
  as DSL interactions, for example `set selectedBar = event.value.index`.
- Focusable SVG interactions synthesize one click for Enter or Space. Native
  buttons use browser activation. Controls receive ARIA labels without duplicate
  labels on their SVG wrappers. Selected bars, cells and tabs have outlines as
  well as color changes. The root SVG is an accessible group.

## Layout and rendering

Absolute layout preserves child coordinates. Row, column and grid layouts add
offsets after expanding repeats and evaluating bound width/height and `when`.
Padding, gap, alignment and justification apply to the resulting visible children.
Stable repetition keys retain instance identity. Duplicate keys fail visibly.
Changing `zIndex` changes SVG painting and hit testing, including root nodes.

Store subscriptions compare each node's bound values independently. A group
arrangement only updates when its layout/order/repeated data change. The browser
regression attaches a DOM observer to an unrelated node and verifies no mutations
while a transformed sibling is dragged. Dynamic expansion has the same 10,000
rendered-node and 32-level limits as the static structure; component recursion and
nested repetitions cannot evade those limits. `Canvas` is explicit and supports
rect/circle collections; the renderer never silently substitutes it for SVG.

Custom scene component templates can reference their supplied `props` in nested
bindings. Registered feature components remain lazy and occupy an HTML region in
the same SVG scene.

## State, data and time

State batch commits are atomic: a failed expression or derived recomputation
restores the previous state/data and does not notify subscribers. Snapshot,
restore, undo and redo retain independent copies. Runtime-derived values activate
after requested plugins register their functions. State Reset preserves current
loaded source data; it resets authored initial state, stops timelines/compute,
clears pointer gestures and pauses/seeks mounted media to zero.

Data sources publish `state._dataStatus.NAME` with loading/error/update status.
Refresh keeps the last valid data on failure, cancels older fetches and ignores
stale responses. Join dependencies initialize in order; cycles fail explicitly.
Repeated SSE/WebSocket refresh replaces its previous connection. Streamed HTTP
payloads are bounded to 8 MiB before complete allocation.

Timeline times and keyframes are milliseconds. `bind` can supply duration, delay,
easing, loop, reverse, or playbackRate. Keyframe times remain absolute if duration
changes. Delays consume only their remaining portion of a frame; looping retains
leftover elapsed time. Reverse playback starts at the end when played from zero.
Play at a completed endpoint restarts; Pause retains position; Stop seeks zero
and restores the configured delay. Seek does not fire playback markers. Reduced
motion reaches the endpoint without continuous movement. Interpolation supports
numbers, arrays, object coordinates, hex colors and structurally compatible SVG
paths. Frame failures reach the visible runtime error boundary.

Audio/video use native media elements, local/allowlisted assets and ordinary DSL
media actions. Playback, pause, seek, rate, volume and mute are supported, with
media events, time bindings, cues and optional timeline synchronization. Seeking
back before a cue enables it to fire again. The tests exercise a local WAV and a
real locally recorded VP8 WebM video.

## Running the evidence

From `runtime/`:

```sh
npm test
npm run test:e2e -- tests/browser/semantics.spec.ts
npm run build
npm run dev -- --port 41976
```

Open `http://127.0.0.1:41976/preview.html?spec=examples/controls.scene.json` to try the
showcase. Playwright captures initial, intermediate, restored and responsive
states under its ignored `test-results/browser` folder. It checks actual state,
geometry, hit targets, media time and input effects; DOM presence alone is not an
interaction pass.
