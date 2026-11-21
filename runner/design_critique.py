"""Early independent art-direction critique of rendered pages, inside the author phase.

The author calls pptx_design_critique with a few page renders (and optional real
reference examples). A fresh model context judges the pictures and returns
concrete, executable revisions. This moves the proven "detailed external
critique -> execute" loop to the start of the deck, before a style propagates.
"""
import json
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from design_inputs import outline_pages, read_deck_plan, read_page_plans
from durable import AppServer, task_configuration
from model_backend import DEFAULT_TASK_MODEL
from progress import read_scoped
from trajectory import record

TOOL = 'pptx_design_critique'
MAX_CALLS = 3  # cover, the first body page that sets the style, final whole-deck pass (2026-11-21: per-page critique duplicated review and added edit loops)
MAX_IMAGES = 6
IMAGE_TYPES = ('.png', '.jpg', '.jpeg', '.webp')

PROMPT = '''You are a demanding art director. A designer has just rendered the slides attached
below ({pages}). You never saw their reasoning; judge only the pictures (any design sheet below states intent, not proof).

The deck: {brief}

{references}{style}{deck_plan}{plans}Standard: what a master of this register would make for exactly this audience and
setting (for restrained genres think Swiss and editorial information design, Vignelli,
FT graphics, Kenya Hara: simple, but every proportion and every empty area decided),
never a generic AI-generated deck and never merely an average example of the genre.
A clean page built from the usual parts (title bar, tinted cards, boxes joined by
lines, dot timelines) is not yet the standard, however tidy; neither is a bare page
where everything sits boxed inside the margins with no recurring graphic device, no
element bleeding, overlapping or breaking the grid, and text set flat. Simple is not
plain.

Registers: restrained genres (lessons, work and weekly reports, academic talks, training)
look best on white or a quiet tint taken from the deck's imagery, with dark text, one primary colour and at most
one accent, real pictures and clear charts, a few graphic devices with a job; standard genres
(proposals, reviews, explainers) add a coloured cover or section style; expressive
genres (product launches, pitches, brand decks) may use bold colour, full-bleed photos
and dark surfaces. Content pages are calmer than the cover in every register. Every page is
held to the craft of a good poster or magazine spread in its register; a restrained page
reaches it by precision, not effects.

The generic AI look is made of defaults. For each page name the elements a generic
AI-generated deck would have made the same way (layout, card, kicker, icon, colour,
equal sizes, centring) and say what a designer would decide instead for this content,
using the attached real references where they apply.

Write in {language}. {audience_check}Start with "DECK DIRECTION": is the register right for this genre and
setting, and keep or change the overall direction (surface and palette, type, image
treatment), in two to four sentences. With three or more pages add "RHYTHM": which pages
carry weight and which rest, and whether they all weigh the same. Then for each page:
"GLANCE": what a viewer takes away in three seconds and where the eye goes first, second
and third, judged from the picture alone (the designer compares it with what the page
was meant to say); a score out of 10 against that standard; "KEEP": the one thing that
works and must survive the changes; and up to six numbered instructions the designer
can execute immediately. Each instruction names the object
or region, the exact change (size, position, colour, crop, replace with a real
photo or a generated illustration or a library icon, delete, regroup, realign) and the
visible result it should produce. Look in particular for: subjects described in text
instead of shown, small or missing pictures, pictograms or objects drawn from
primitive shapes, the same card grid repeated, default-looking palettes (navy or dark
"tech" themes on unrelated subjects), weak focal point, crowded or empty areas,
misalignment, unattached labels, small text for the viewing setting. Skip what is
already good; do not praise. No facts or content changes beyond presentation.

Fixed project constraints (never suggest otherwise): fonts are {fonts}, with hierarchy
from size, spacing and the available weights; a tinted ground is fine when it is the deck's
declared background in deck-style.json (taken from its imagery or references), never a
default off-white; slides stay native and editable.
'''


def enabled(cfg):
    return cfg.get('design_critique', True) is not False and not cfg.get('_customer_funded')


class DesignCritique:
    def __init__(self, cfg, job, *, tick=None, trajectory=None, reporter=None):
        self.cfg = cfg; self.job = Path(job).resolve(strict=True)
        self.tick = tick; self.trajectory = trajectory; self.reporter = reporter
        self.folder = self.job / 'design-critique'
        self.lock = threading.Lock(); self.started = 0; self.ready = []; self.running = 0
        self.previous = len(list(self.folder.glob('*.json'))) if self.folder.is_dir() else 0

    def specs(self):
        return [{'type': 'function', 'name': TOOL, 'description': (
            'Independent art-director critique of rendered pages by a fresh reviewer. Pass task-local render images and '
            'optionally real reference examples of this genre. By default it runs in the background and returns at once: '
            'keep working, and the finished instructions arrive with your next pptx_page_design_context result (or the '
            'next call of this tool). Set wait=true to block for the result, e.g. for the final whole-deck pass. '
            'At most three requests per task: the cover, the first body page that sets the style, and a final whole-deck pass; other pages need none.'),
            'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['images'], 'properties': {
                'images': {'type': 'array', 'minItems': 1, 'maxItems': MAX_IMAGES, 'items': {'type': 'string'},
                           'description': 'Task-relative paths of page renders, in page order.'},
                'pages': {'type': 'array', 'items': {'type': 'integer'},
                          'description': 'Page numbers of those renders. Pass these when reviewing a subset so the critic receives the matching design sheets.'},
                'reference_images': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string'},
                                     'description': 'Optional task-relative images of real examples to compare against.'},
                'wait': {'type': 'boolean', 'description': 'Block until the critique is ready (default false).'}}}}]

    def deliver(self):
        """Finished background critiques not yet handed to the author, as one text block."""
        with self.lock:
            ready, self.ready = self.ready, []
            running = self.running
        if not ready:
            return ''
        text = '\n\n'.join(ready)
        tail = f' {running} more critique(s) still running.' if running else ''
        return ('INDEPENDENT DESIGN CRITIQUE (arrived in the background; apply with edit_objects and render the affected '
                'pages again):' + tail + '\n\n' + text)

    @staticmethod
    def reply(ok, text):
        return {'success': ok, 'contentItems': [{'type': 'inputText', 'text': text}]}

    def _image(self, name):
        path = (self.job / name).resolve(strict=True)
        if not path.is_relative_to(self.job) or path.suffix.lower() not in IMAGE_TYPES or not path.is_file():
            raise ValueError(f'{name}: use a task-local PNG/JPEG/WebP file')
        return path

    def _registered_references(self):
        """Real works the author inspected and registered, so the critic compares against them."""
        try:
            plan = json.loads(read_scoped(self.job, 'decision-plan.json', 2 * 1024 * 1024))
        except (OSError, ValueError):
            return []
        found = []
        for ref in plan.get('references') or []:
            evidence = ref.get('evidence') if isinstance(ref, dict) else None
            if isinstance(evidence, str) and ref.get('inspection') == 'local_image':
                try:
                    found.append(self._image(evidence))
                except (OSError, ValueError):
                    continue
            if len(found) == 3:
                break
        return found

    def handle(self, params):
        args = params.get('arguments') or {}
        with self.lock:
            if self.previous + self.started >= MAX_CALLS:
                return self.reply(False, 'Design critique limit reached for this task; apply the earlier instructions.')
        try:
            images = [self._image(n) for n in args.get('images') or []][:MAX_IMAGES]
            references = [self._image(n) for n in args.get('reference_images') or []][:3]
        except (OSError, ValueError) as error:
            return self.reply(False, str(error))
        if not images:
            return self.reply(False, 'Pass at least one rendered page image.')
        if not references:
            references = self._registered_references()
        pages = args.get('pages') or list(range(1, len(images) + 1))
        with self.lock:
            self.started += 1
        if args.get('wait'):
            reply = self._run(images, references, pages, self.tick)
            earlier = self.deliver()
            if earlier:
                reply['contentItems'][0]['text'] = earlier + '\n\n' + reply['contentItems'][0]['text']
            return reply
        with self.lock:
            self.running += 1
        def background():
            try:
                reply = self._run(images, references, pages, None, report=False)
                text = reply['contentItems'][0]['text']
            except Exception as error:  # a failed critique must never break authoring
                text = f'Critique of pages {pages} failed ({type(error).__name__}); continue with your own render check.'
            with self.lock:
                self.ready.append(f'[pages {", ".join(map(str, pages))}]\n' + text)
                self.running -= 1
        threading.Thread(target=background, name='pptx-design-critique', daemon=True).start()
        earlier = self.deliver()
        return self.reply(True, (earlier + '\n\n' if earlier else '') + f'Critique of pages {pages} started in the background. '
                          'Keep working; its instructions will arrive with your next pptx_page_design_context result.')

    def _run(self, images, references, pages, tick, report=True):
        request = json.loads(read_scoped(self.job, 'request.json', 200000))
        brief = json.dumps({k: request.get(k) for k in ('title', 'brief', 'style', 'pages', 'language') if request.get(k)},
                           ensure_ascii=False)[:6000]
        language = {'zh-CN': 'Simplified Chinese'}.get(request.get('language'), 'the deck language')
        ident = uuid.uuid4().hex; started = time.monotonic()
        record(self.trajectory, 'emit', 'design_critique.request', {'id': ident, 'images': [str(p.relative_to(self.job)) for p in images]})
        if self.reporter and report:
            self.reporter.event('working', 'Independent design critique of the first rendered pages', state='started', category='review')
        with tempfile.TemporaryDirectory(prefix='pptx-critique-') as temp:
            work = Path(temp).resolve()
            copies = []; copies_source = []
            for i, path in enumerate(references + images):
                target = work / f'{i:02d}{path.suffix.lower()}'; shutil.copyfile(path, target); copies.append(target)
                copies_source.append((path, target.name))
            ref_text = ('The first %d attached image(s) are real reference examples of this genre; the rest are the '
                        'designer\'s pages.\n\n' % len(references)) if references else ''
            style = ''
            try:
                deck = json.loads(read_scoped(self.job, 'deck-style.json', 20000))
                style = ('The designer\'s deck-style.json: register ' + str(deck.get('register')) + ', colours '
                         + json.dumps(deck.get('colors'), ensure_ascii=False)
                         + ((', planned rhythm ' + json.dumps(deck['rhythm'], ensure_ascii=False)) if isinstance(deck.get('rhythm'), dict) else '')
                         + ((', graphic devices ' + json.dumps(deck['devices'], ensure_ascii=False)) if isinstance(deck.get('devices'), dict) else '')
                         + '. Point out pages that drift from it.\n\n')
            except (OSError, ValueError):
                pass
            deck_plan = audience_check = ''
            try:
                saved = read_deck_plan(self.job)
                if saved:
                    deck_plan = ('The author\'s occasion and audience sheet (deck-plan.json):\n'
                                 + json.dumps({field: saved.get(field) for field in (
                                     'occasion', 'audience', 'feeling', 'expectations', 'wrong_looks')}, ensure_ascii=False)
                                 + '\n\n')
                    audience_check = ('In the first sentence of "DECK DIRECTION", answer based only on the attached rendered pages whether the deck '
                                      'makes this audience feel the intended feeling, shows what is in expectations, and falls into '
                                      'any of wrong_looks. ')
            except (OSError, ValueError):
                pass
            plans = ''
            try:
                saved = read_page_plans(self.job)
                if saved:
                    outline = outline_pages(self.job)
                    selected = {n: saved[outline[n - 1]['id']] for n in pages[:len(images)]
                                if type(n) is int and 1 <= n <= len(outline) and outline[n - 1]['id'] in saved}
                    if selected:
                        plans = ('Saved design sheets by slide number:\n' + json.dumps(selected, ensure_ascii=False)
                                 + '\nKeep GLANCE based on the picture alone. In the existing critique for each page '
                                   'with a visual_idea, answer whether visual_idea is actually visible in the image '
                                   'and name the visual evidence.\n\n')
            except (OSError, ValueError):
                pass
            from font_assets import deployment_defaults
            fonts = deployment_defaults()
            prompt = PROMPT.format(pages='pages ' + ', '.join(map(str, pages)), brief=brief, references=ref_text, language=language, style=style,
                                   deck_plan=deck_plan, audience_check=audience_check, plans=plans,
                                   fonts=f"{fonts['east_asian']} for Chinese and {fonts['latin']} for Latin text, plus DengXian (等线, "
                                         f"light/regular/bold) and Arial for headings, numbers and display text")
            text = backend = None
            # A second model's eye (2026-11-21): Claude critiques when available; GPT is the fallback.
            if self.cfg.get('critique_backend') == 'claude':
                import claude_vision
                if claude_vision.available(self.cfg):
                    try:
                        answer = claude_vision.ask(self.cfg, prompt, copies)
                        text, backend = answer['text'][:20000], 'claude:' + answer['model']
                        record(self.trajectory, 'emit', 'design_critique.claude', {'id': ident, 'usage': answer['usage'],
                                                                                   'seconds': answer['seconds']})
                    except claude_vision.ClaudeUnavailable as error:
                        record(self.trajectory, 'emit', 'design_critique.fallback', {'id': ident, 'reason': str(error)})
        if text is None:
          with tempfile.TemporaryDirectory(prefix='pptx-critique-gpt-') as temp:
            work = Path(temp).resolve()
            for path in copies_source:
                shutil.copyfile(path[0], work / path[1])
            copies = [work / name for _, name in copies_source]
            config = task_configuration(work, web_search='disabled')
            config['model'] = self.cfg.get('default_model', DEFAULT_TASK_MODEL)
            # Runs in the background, so a deeper look costs the author no waiting.
            config['model_reasoning_effort'] = self.cfg.get('critique_reasoning_effort', 'high')
            meter = self.cfg.get('_usage_ledger')
            usage = {'on_usage': meter.codex_sink(self.cfg.get('_usage_stage', 'author') + '.design_critique', config['model'])} if meter else {}
            with AppServer(cwd=work, config=config, tick=tick, **usage) as server:
                thread = server.start_thread()['thread']['id']
                turn = server.start_turn(thread, prompt, images=copies)['id']
                result = server.wait_turn(thread, turn, timeout=300)
                if result.get('status') != 'completed':
                    return self.reply(False, 'Design critique did not complete; continue with your own render check.')
                text = server.result_text(thread, turn)[:20000]
            backend = 'gpt:' + config['model']
        self.folder.mkdir(exist_ok=True)
        (self.folder / f'{ident}.json').write_text(json.dumps({'pages': pages, 'critique': text, 'backend': backend,
            'seconds': round(time.monotonic() - started, 1)}, ensure_ascii=False, indent=1))
        record(self.trajectory, 'emit', 'design_critique.result', {'id': ident, 'pages': pages, 'chars': len(text)})
        if self.reporter and report:
            self.reporter.event('edited', 'Design critique returned', state='completed', category='review')
        return self.reply(True, text + '\n\nApply these instructions (edit_objects, then render and check again); carry '
                          'deck-direction changes into all later pages.')
