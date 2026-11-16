"""Optional, host-side separation of local development and server deployment.

Existing unlabelled installations keep their HTTPS-only configuration. A marked
checkout cannot silently switch profiles via inherited environment variables.
This is configuration validation, not the task filesystem/network sandbox.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit


def validate(cfg, worker, *, expected=None, platform=None):
    worker = Path(worker).resolve()
    marker = worker / 'deployment.local.json'
    pinned = json.loads(marker.read_text()).get('environment') if marker.is_file() else None
    profile = cfg.get('deployment_environment')
    for value in (profile, pinned, expected):
        if value is not None and value not in ('local', 'server'):
            raise ValueError('Unknown deployment environment')
    if any(value is not None and value != profile for value in (pinned, expected)):
        raise ValueError('Settings do not match the selected deployment environment')
    try:
        site = urlsplit(cfg.get('site', ''))
        port = site.port
    except ValueError:
        raise ValueError('Invalid worker site origin') from None
    if (not site.hostname or site.username is not None or site.password is not None
            or site.query or site.fragment or site.path not in ('', '/')
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError('Worker site must be an origin without credentials or a path')
    local = site.hostname in ('localhost', '127.0.0.1', '::1')
    if profile == 'local':
        if not local or site.scheme not in ('http', 'https'):
            raise ValueError('Local development may only use a loopback website')
        if cfg.get('site_http_transport', 'curl') != 'curl':
            raise ValueError('Local development uses the existing curl transport')
        if cfg.get('site_http_proxy'):
            raise ValueError('Do not proxy local queue traffic')
    elif site.scheme != 'https':
        raise ValueError('HTTPS required outside explicit local development')
    if profile == 'server':
        if (platform or sys.platform) != 'linux':
            raise ValueError('Server deployment requires Linux')
        if local:
            raise ValueError('Server deployment requires its hosted website origin')
    if profile:
        # Runtime/state belong to this checkout, rather than the other worker's
        # live directories. The interpreter and read-only template may be external.
        for key in ('plugin', 'state_directory'):
            value = cfg.get(key)
            if not value or not Path(value).is_absolute():
                raise ValueError(f'{key} must be an absolute path for this checkout')
            path = Path(value).resolve()
            if not path.is_relative_to(worker):
                raise ValueError(f'{key} must stay inside this checkout runner directory')
        if not Path(cfg['plugin']).resolve().is_relative_to(worker / 'runtime'):
            raise ValueError('Use a staged runtime instead of editing a running plugin')
        if Path(cfg['state_directory']).resolve() == worker:
            raise ValueError('State must have its own directory')
    return profile or 'legacy'
