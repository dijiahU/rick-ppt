"""Load host-only workflow modules without shadowing the legacy workflow entrypoint."""
import importlib.util
from pathlib import Path
import sys


def _load(name, filename):
    if name in sys.modules:
        return sys.modules[name]
    source = Path(__file__).resolve().parent.parent / 'workflow' / filename
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError('Durable workflow runtime is unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


journal_module = _load('pptx_host_journal', 'journal.py')
transport_module = _load('pptx_host_app_server', 'app_server.py')
Journal = journal_module.Journal
# Interactive decks retain native renders, scene captures and earlier versions.
# Keep bounded host budgets large enough to checkpoint those complete histories.
# Individual file, record and integrity checks remain the journal defaults.
HOST_JOURNAL_LIMITS = journal_module.Limits(total_bytes=4 * 1024**3, files=100000)
JournalError = journal_module.JournalError
AppServer = transport_module.AppServer
RPCError = transport_module.RPCError
TransportError = transport_module.TransportError
task_configuration = transport_module.task_configuration
redact_text = transport_module.redact_text
