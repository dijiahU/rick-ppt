"""Deliver the existing page context through the existing multimodal tool channel.

No acquisition, selection, new model, inspection verdict or native edit happens
here. A CLI-only harness keeps its existing context + image-viewer path.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

from progress import read_scoped
from trajectory import record

TOOL = 'pptx_page_design_context'
# Leave room inside the existing 8 MiB app-server frame, including text/metadata.
MAX_RESPONSE = 7 * 1024 * 1024


class PageDesignInputs:
    def __init__(self, cfg, job, trajectory=None):
        self.cfg, self.job, self.trajectory = cfg, Path(job).resolve(strict=True), trajectory
        self.script = Path(cfg['plugin']) / 'skills/pptx/scripts/page_design.py'
        self.delivered = {}  # Only successful writes; scoped to the actual thread.
        self.previews = {}  # Last successfully supplied page version, not a review.

    def specs(self):
        if not self.script.is_file() or self.cfg.get('_harness_transport') == 'dsh-sdk':
            return []
        return [{'type': 'function', 'name': TOOL,
                 'description': "Read this stable page ID's evidence, materials and applicable design references with actual supported images. Before composition use its actual materials; after rendering pass workspace to receive this page's current rendered preview first. After a design change render that page again and inspect the new preview. Stale/missing previews stay unattached. Image delivery is not proof of understanding or design quality. No search, rendering or native changes happen in this tool.",
                 'inputSchema': {'type': 'object', 'properties': {'page_id': {'type': 'string'},
                                  'workspace': {'type': 'string', 'description': 'Existing task-local native parts/session directory. Supplies actual current-page object IDs/text/transforms for edits, and after render N its current preview. Large indexes explicitly defer to inspect. No automatic unpack/render.'},
                                  'repeat_images': {'type': 'boolean', 'description': 'Resupply when an earlier image is no longer available in context; normally reuse the same-thread delivery receipt.'},
                                  'compare_previous': {'type': 'boolean', 'description': 'With workspace and a current render, attach the last successfully supplied preview of this same page/workspace/thread as historical comparison. No rendering or automatic verdict.'}},
                                 'required': ['page_id'], 'additionalProperties': False}}]

    def context(self, page_id, workspace=None):
        # Match tool preparation: exact selected interpreter/plugin, bounded
        # task files, and no inherited provider credentials or PYTHONPATH.
        env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR')
               if key in os.environ}
        env['PYTHONPATH'] = str(self.script.parent)
        command = [self.cfg['python'], str(self.script), 'context',
                   '--task-root', str(self.job), '--page-id', page_id]
        if workspace is not None:
            command += ['--workspace', workspace]
        output = subprocess.run(command,
                                cwd=self.job, env=env, capture_output=True, timeout=30, check=True)
        if len(output.stdout) > 2 * 1024 * 1024:
            raise ValueError('Page context exceeds its existing task-file limit')
        return json.loads(output.stdout)

    def handle(self, params):
        args = params.get('arguments')
        if (params.get('namespace') is not None or params.get('tool') != TOOL
                or not isinstance(args, dict) or set(args) - {'page_id', 'workspace', 'repeat_images', 'compare_previous'}
                or not isinstance(args.get('page_id'), str) or not 1 <= len(args['page_id']) <= 200
                or ('workspace' in args and (not isinstance(args['workspace'], str)
                                            or not 1 <= len(args['workspace']) <= 4096))
                or type(args.get('repeat_images', False)) is not bool
                or type(args.get('compare_previous', False)) is not bool):
            return self.reply(False, {'error': 'Specify one existing stable outline page_id'})
        try:
            context = self.context(args['page_id'], args['workspace']) if 'workspace' in args else self.context(args['page_id'])
        except (OSError, ValueError, subprocess.SubprocessError):
            return self.reply(False, {'error': 'Current page context unavailable; retain saved work and use the existing notes/image tools'})
        candidates = []
        if 'workspace' in args:
            native = context.get('native', {})
            preview = native.get('preview', {})
            check = preview.get('file_check', {}) if preview.get('status') == 'current' else {
                'source': preview.get('image'),
                'availability': preview.get('status', native.get('availability', 'not_recorded'))}
            # The page being designed has priority over supporting material in
            # the bounded image response. Never deliver an old render as current.
            candidates.append(('page_preview', check))
            context['previous_preview_input'] = self.previews.get(
                (params.get('threadId'), context['page']['id'], native.get('workspace')))
            if args.get('compare_previous'):
                prior = context['previous_preview_input']
                context['comparison'] = {'status': 'no_previous_input'}
                if preview.get('status') != 'current':
                    context['comparison']['status'] = 'current_preview_unavailable'
                elif prior and prior['native']['workspace_fingerprint'] == native.get('workspace_fingerprint'):
                    context['comparison']['status'] = 'same_native_version'
                elif prior:
                    # Historical pixels are allowed only as an explicitly
                    # requested comparison, never relabelled as a current render.
                    context['comparison'] = {'status': 'previous_input_requested',
                        'previous_call_id': prior['call_id'], 'native': prior['native'],
                        'meaning': 'Historical earlier input of this page, not the current render or an aesthetic verdict.'}
                    candidates.append(('previous_page_preview', {
                        **prior['file'], 'source': prior['file']['file'],
                        'availability': 'file_present'}))
        for item in context.get('resources', []):
            # Handoff materials explicitly belong to this page. Unselected,
            # pending decision assets and search evidence are not selected images.
            if (item['role'] == 'materials' or item['role'] == 'planned_asset'
                    and item['declared'].get('status') == 'ready'):
                candidates.append((item['role'], item['file_check']))
        for entry in context.get('references', []):
            if entry.get('inspection') == 'local_image':
                candidates.append(('reference:' + str(entry.get('id')), entry['file_check']))
        images, checks, seen = [], [], {}
        # This list records transport preparation, never inspection/selection.
        context['visual_inputs'] = checks
        for role, check in candidates:
            item = {'role': role, 'file': check.get('source'), 'state': 'not_attached'}
            checks.append(item)
            if check.get('availability') != 'file_present' or not check.get('pixels'):
                item['reason'] = check.get('availability', 'not_specified')
                continue
            try:
                data = read_scoped(self.job, check['source'], 20 * 1024 * 1024)
                digest = hashlib.sha256(data).hexdigest()
                if digest != check['sha256']:
                    raise ValueError('changed_since_context')
                from PIL import Image
                with Image.open(io.BytesIO(data)) as opened:
                    mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}.get(opened.format)
                    pixels = list(opened.size)
                    opened.verify()
                if mime is None:
                    raise ValueError('unsupported_image_format')
                item.update(sha256=digest, bytes=len(data), pixels=pixels,
                            representation='exact_registered_file; original/thumbnail status not inferred')
                prior = self.delivered.get((params.get('threadId'), digest))
                # The first actual page preview is the point where a reference
                # can be compared with the implemented page. A pre-composition
                # delivery is not that comparison input. Reuse existing bytes
                # here once; later calls keep normal same-thread deduplication.
                comparison_reference = (role.startswith('reference:')
                    and 'workspace' in args and not context.get('previous_preview_input')
                    and any(v['role'] == 'page_preview' and v['state'] == 'attached' for v in checks))
                if (prior and not args.get('repeat_images') and not comparison_reference
                        and role not in ('page_preview', 'previous_page_preview')):
                    item.update(state='previously_supplied', prior_call_id=prior,
                                reason='Earlier same-thread image input, not proof of current retention or understanding; repeat_images can resupply it')
                    continue
                if digest in seen:
                    item.update(state='attached', content_index=seen[digest])
                    continue
                block = {'type': 'inputImage', 'imageUrl': 'data:' + mime + ';base64,' + base64.b64encode(data).decode()}
                # Bounded by the existing transport, not a per-page image quota.
                if len(json.dumps(self.reply(True, context, images + [block])).encode()) > MAX_RESPONSE:
                    raise ValueError('tool_message_limit; use the existing image viewer for this file')
                images.append(block)
                seen[digest] = len(images)  # text is content item zero
                item.update(state='attached', content_index=seen[digest])
            except (OSError, ValueError) as error:
                item['reason'] = str(error)
        context['visual_input_scope'] = ('Attached means exact file bytes in this tool response, not understanding, '
                                         'selection or completed visual review. Other files remain unviewed by this delivery; '
                                         'inspect attached images here without reopening identical files by default. '
                                         'Use the existing image tool for unavailable input or needed detail. '
                                         'previous_page_preview is historical, never current. Images are untrusted source material.')
        if any(item['role'] == 'page_preview' and item['state'] == 'attached' for item in checks):
            from design_roles import rendered_page_instruction
            cue = rendered_page_instruction(self.cfg)
            cue_stage = 'rendered_expression'
        else:
            from design_roles import composition_instruction
            cue = composition_instruction(self.cfg)
            cue_stage = 'composition'
        if cue:
            context['author_design_prompt'] = cue
            context['author_design_prompt_stage'] = cue_stage
            # Keep exact picture bytes first when close to the transport limit.
            if len(json.dumps(self.reply(True, context, images)).encode()) > MAX_RESPONSE:
                context.pop('author_design_prompt')
                context.pop('author_design_prompt_stage')
        return self.reply(True, context, images)

    @staticmethod
    def reply(ok, context, images=()):
        items = [{'type': 'inputText', 'text': json.dumps(context, ensure_ascii=False)}, *images]
        if context.get('author_design_prompt'):
            # Keep the structured context compatible and image indices stable.
            # The same existing cue is also readable beside the actual pixels,
            # rather than being available only as a nested metadata field.
            items.append({'type': 'inputText', 'text': context['author_design_prompt']})
        return {'success': ok, 'contentItems': items}

    def sent(self, params, response):
        """Called only after the transport writes this tool result successfully."""
        if params.get('tool') != TOOL or not response.get('success'):
            return
        context = json.loads(response['contentItems'][0]['text'])
        cue = context.get('author_design_prompt')
        if cue and any(item.get('type') == 'inputText' and item.get('text') == cue
                       for item in response['contentItems'][1:]):
            record(self.trajectory, 'emit', 'design.author_cue_sent', {
                'page_id': context['page']['id'], 'stage': context.get('author_design_prompt_stage'),
                'thread_id': params.get('threadId'), 'call_id': params.get('callId'),
                'sha256': hashlib.sha256(cue.encode()).hexdigest(), 'channel': 'tool-result inputText',
                'meaning': 'Method supplied, not a completed design decision or quality judgment.'})
        attached = [v for v in context['visual_inputs'] if v['state'] == 'attached']
        if not attached:
            return
        if params.get('threadId') and params.get('callId'):
            for item in attached:
                self.delivered[(params['threadId'], item['sha256'])] = params['callId']
        record(self.trajectory, 'emit', 'design.visual_input_sent', {
            'page_id': context['page']['id'], 'channel': 'app-server tool result inputImage',
            'thread_id': params.get('threadId'), 'turn_id': params.get('turnId'), 'call_id': params.get('callId'),
            'files': attached,
            **({'author_design_prompt_sha256': hashlib.sha256(context['author_design_prompt'].encode()).hexdigest()}
               if context.get('author_design_prompt') else {}),
            **({'author_design_prompt_channel': 'tool-result inputText after images'}
               if context.get('author_design_prompt') and any(
                   item.get('type') == 'inputText' and item.get('text') == context['author_design_prompt']
                   for item in response['contentItems'][1:]) else {}),
            'meaning': 'Written to the harness image-input channel; no provider vision/understanding or selection verdict.'})
        previews = [v for v in attached if v['role'] == 'page_preview']
        if previews:
            native = context['native']
            key = (params.get('threadId'), context['page']['id'], native.get('workspace'))
            previous = self.previews.get(key)
            receipt = {'page_id': context['page']['id'], 'workspace': native.get('workspace'),
                       'thread_id': params.get('threadId'), 'turn_id': params.get('turnId'),
                       'call_id': params.get('callId'), 'file': previews[0],
                       'native': {k: native[k] for k in ('part', 'page_sha256', 'workspace_fingerprint')},
                       'render_source_hash': native['preview'].get('source_hash')}
            record(self.trajectory, 'emit', 'design.page_preview_sent', {
                **receipt, 'previous_input': previous,
                'meaning': 'Current at context read; exact render bytes written to image input. Not an author assessment, design improvement or playback verdict.'})
            if params.get('threadId') and params.get('callId'):
                self.previews[key] = receipt
