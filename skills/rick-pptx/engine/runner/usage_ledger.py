"""Private, durable usage receipts. Never inferred from text or exposed to a task.

API receipts are counted once per upstream response. Codex turn receipts are a
separate, non-API series. Prices are optional host-owned contract rates, frozen
with each receipt; absence of a price/receipt is never represented as zero cost.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit


def marker(value, limit=200):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,'+str(limit)+'}', value) else None


def count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def normalize_usage(usage):
    usage = usage if isinstance(usage, dict) else {}
    inp = count(usage.get('input_tokens', usage.get('prompt_tokens')))
    out = count(usage.get('output_tokens', usage.get('completion_tokens')))
    details = usage.get('input_tokens_details', usage.get('prompt_tokens_details')) or {}
    output_details = usage.get('output_tokens_details', usage.get('completion_tokens_details')) or {}
    if not isinstance(details, dict) or not isinstance(output_details, dict):
        return None
    cached = count(usage.get('cached_input_tokens', details.get('cached_tokens', 0)))
    written = count(details.get('cache_write_tokens', 0))
    reasoning = count(usage.get('reasoning_output_tokens', output_details.get('reasoning_tokens', 0)))
    # Native Anthropic input_tokens excludes cache reads/writes, unlike OpenAI.
    if 'cache_read_input_tokens' in usage or 'cache_creation_input_tokens' in usage:
        cached = count(usage.get('cache_read_input_tokens', 0))
        written = count(usage.get('cache_creation_input_tokens', 0))
        if inp is not None and cached is not None and written is not None:
            inp += cached + written
    if any(x is None for x in (inp, out, cached, written, reasoning)) or cached+written > inp or reasoning > out:
        return None
    return dict(inputTokens=inp, outputTokens=out, cachedInputTokens=cached,
                cacheWriteTokens=written, reasoningTokens=reasoning, totalTokens=inp+out)


def price_usage(usage, provider, model, tier, prices):
    if usage is None:
        return None
    for rate in prices.get('rates', []):
        if not isinstance(rate, dict):
            continue
        if (rate.get('provider'), rate.get('model'), rate.get('serviceTier', 'default')) != (provider, model, tier):
            continue
        try:
            fields = ('inputUsdPerMillion', 'cachedInputUsdPerMillion', 'cacheWriteUsdPerMillion', 'outputUsdPerMillion')
            values = [Decimal(str(rate[k])) for k in fields]
            if any(not v.is_finite() or v < 0 or v > 1000000 for v in values):
                return None
            units = (usage['inputTokens']-usage['cachedInputTokens']-usage['cacheWriteTokens'],
                     usage['cachedInputTokens'], usage['cacheWriteTokens'], usage['outputTokens'])
            # USD per million tokens * tokens = micro-USD. Reasoning is already
            # included in output, and cached tokens are already included in input.
            amount = int(sum(v*n for v, n in zip(values, units)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            if not marker(prices.get('version')) or amount > 10**15:
                return None
            return {'costMicrousd': amount, 'priceVersion': prices['version'],
                    'priceSnapshot': {k: format(v, 'f') for k, v in zip(fields, values)}}
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None
    return None


class UsageLedger:
    def __init__(self, cfg, task, send):
        self.cfg, self.task, self.send = cfg, task, send
        self.root = Path(cfg.get('state_directory', Path(__file__).parent/'state'))/task['id']/'usage'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.send_lock = threading.Lock()
        self.records, self.pending = {}, {}
        self.prices = {}
        path = cfg.get('usage_pricing_file')
        if path:
            self.prices = json.loads(Path(path).read_text())
            if not isinstance(self.prices, dict) or not isinstance(self.prices.get('rates', []), list):
                raise ValueError('Invalid host usage price configuration')
        for file in self.root.glob('*.json'):
            row = json.loads(file.read_text())
            self.records[row['id']] = row
            self.pending[row['id']] = row
        self.attempt = hashlib.sha256(task['lease'].encode()).hexdigest()[:16]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name='pptx-usage-upload')
        self.thread.start()

    def _save(self, row):
        with self.lock:
            previous = self.records.get(row['id'])
            if previous:
                if previous['source'] == 'api':
                    return  # Immutable upstream receipt, including its rate snapshot.
                row['attempt'], row['stage'] = previous['attempt'], previous['stage']
                if previous['usageStatus'] == 'reported':
                    for key in ('inputTokens','outputTokens','cachedInputTokens','cacheWriteTokens','reasoningTokens'):
                        row[key] = max(previous[key], row[key] or 0)
                    row['totalTokens'] = row['inputTokens']+row['outputTokens']
                    row['usageStatus'] = 'reported'
                if previous.get('outcome') == 'completed':
                    row['outcome'] = 'completed'
                if all(row.get(k) == v for k, v in previous.items() if k not in ('version', 'at')):
                    return
                row['at'] = previous['at']
            row['version'] = previous['version']+1 if previous else 1
            temporary = self.root/('.pending-'+uuid.uuid4().hex)
            with os.fdopen(os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as stream:
                json.dump(row, stream, ensure_ascii=False, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root/(row['id']+'.json'))
            self.records[row['id']] = row
            self.pending[row['id']] = row

    def _base(self, identity, stage, source, provider, model, protocol, usage):
        row = dict(id=hashlib.sha256(identity.encode()).hexdigest(), attempt=self.attempt,
                   stage=marker(stage, 100) or 'unknown', source=source,
                   provider=marker(provider, 253) or 'unknown', model=marker(model) or 'unknown',
                   protocol=protocol, usageStatus='reported' if usage else 'unavailable',
                   at=int(time.time()*1000), version=1, costMicrousd=None,
                   costSource='not_api' if source == 'codex' else 'unpriced', priceVersion=None,
                   priceSnapshot=None, serviceTier='default')
        row.update(usage or dict.fromkeys(('inputTokens', 'outputTokens', 'cachedInputTokens',
                                         'cacheWriteTokens', 'reasoningTokens', 'totalTokens')))
        return row

    def api_sink(self, stage, profile):
        provider = urlsplit(profile['base_url']).netloc
        # Origin/path hash separates different accounts/routes on the same host
        # without retaining keys, URLs or account identities in the receipt.
        route = hashlib.sha256((profile['base_url']+'\0'+profile['api_key']).encode()).hexdigest()
        def observe(call):
            if call.get('cache_hit'):
                return  # Adapter replay protection is not an upstream request.
            response_id = marker(call.get('response_id'))
            request_id = marker(call.get('request_id'))
            identity = 'api:'+route+':'+(response_id or request_id or uuid.uuid4().hex)
            usage = normalize_usage(call.get('usage'))
            model = call.get('response_model') or profile['model']
            row = self._base(identity, stage, 'api', provider, model, profile.get('wire_api', 'responses'), usage)
            outcome = call.get('response_status')
            if outcome not in ('completed','failed','incomplete'):
                outcome = 'completed' if call.get('finish_reason') in ('stop','tool_calls') else 'incomplete' if call.get('finish_reason') == 'length' else 'unknown'
            row.update(responseId=response_id, requestId=request_id, outcome=outcome)
            # The sink receives the proxy's allowlisted numerical usage only.
            # Preserve provider field names for later invoice reconciliation.
            row['rawUsage'] = call.get('usage') or None
            tier = call.get('actual_service_tier') or profile.get('service_tier', 'default')
            row['serviceTier'] = 'priority' if tier == 'fast' else tier
            priced = price_usage(usage, provider, model, row['serviceTier'], self.prices)
            if priced:
                row.update(priced, costSource='configured_rate')
            self._save(row)
        return observe

    def codex_sink(self, stage, model):
        def observe(event):
            thread, turn = marker(event.get('thread_id')), marker(event.get('turn_id'))
            if not thread or not turn:
                return
            usage = normalize_usage(event.get('usage'))
            identity = 'codex:'+thread+':'+turn
            row = self._base(identity, stage, 'codex', 'codex', model, 'codex', usage)
            row['outcome'] = event.get('status') if event.get('status') in ('completed','failed','interrupted') else 'unknown'
            self._save(row)
        return observe

    def flush(self):
        if not self.send_lock.acquire(blocking=False):
            return
        try:
            with self.lock:
                rows = list(self.pending.values())[:25]
            if not rows:
                return
            result = self.send(self.cfg, f'/api/worker/{self.task["id"]}/usage?action=usage',
                               json.dumps({'version': 1, 'records': rows}).encode(), self.task['lease'])
            if result.get('ok') is True:
                with self.lock:
                    for row in rows:
                        if self.pending.get(row['id']) == row:
                            self.pending.pop(row['id'], None)
        finally:
            self.send_lock.release()

    def _loop(self):
        while not self.stop.wait(5):
            try:
                self.flush()
            except Exception:
                pass  # Durable rows remain pending; telemetry never reruns a task.

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        try:
            # Bound shutdown work; remaining host receipts replay on task resume.
            for _ in range(8):
                if not self.pending:
                    break
                self.flush()
        except Exception:
            print('Usage upload pending; private receipts retained for recovery.', flush=True)
