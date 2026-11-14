"""Fail-closed Landlock/seccomp adapter for namespace-restricted Linux hosts.

Each task runs with a separate uid, task-only writes and no sockets, including
abstract Unix sockets. This does not implement namespaces or Docker.
"""
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import resource
import stat

LIBC = ctypes.CDLL(None, use_errno=True)
READ = (1 << 0) | (1 << 2) | (1 << 3)
WRITE = (1 << 13) - 1
SYSTEM_READS = ['/usr', '/bin', '/sbin', '/lib', '/lib64', '/etc',
                '/root/miniconda3/bin/python3.12', '/root/miniconda3/lib/python3.12',
                '/root/miniconda3/lib/libexpat.so.1.9.2']

class Ruleset(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]

class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]

def checked(result, operation):
    if result < 0:
        raise OSError(ctypes.get_errno(), operation)
    return result

def own_workspace(root, uid):
    for directory, dirs, files, fd in os.fwalk(root, follow_symlinks=False):
        owner=os.fstat(fd)
        if (owner.st_uid,owner.st_gid)!=(uid,uid):os.fchown(fd, uid, uid)
        for name in dirs + files:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError('Hard-linked workspace file is not supported')
            if (info.st_uid,info.st_gid)!=(uid,uid):
                os.chown(name, uid, uid, dir_fd=fd, follow_symlinks=False)

def restrict(root, reads=(), *, writes=(), local_socket_server=False, run_uid=None):
    root = Path(root).resolve(strict=True)
    if root == Path('/') or not str(root).startswith('/tmp/pptx-'):
        raise ValueError('An isolated temporary PPTX workspace is required')
    abi = checked(LIBC.syscall(444, 0, 0, 1), 'Landlock is required')
    handled = WRITE | ((1 << 13) if abi >= 2 else 0) | ((1 << 14) if abi >= 3 else 0)
    ruleset = Ruleset(handled)
    fd = checked(LIBC.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0), 'Landlock create')
    uid = 100000 + int.from_bytes(hashlib.sha256(str(root).encode()).digest()[:4], 'big') % 1000000000
    if run_uid is not None:uid=run_uid
    if os.geteuid() == 0:
        own_workspace(root, uid)
    paths = [(p, READ) for p in [*SYSTEM_READS, *reads]]
    paths += [(root, handled), *((p, handled) for p in writes)]
    paths += [(p, READ | (1 << 1)) for p in ['/dev/null', '/dev/zero', '/dev/random', '/dev/urandom']]
    try:
        for path, access in paths:
            path = Path(path)
            if not path.exists():
                continue
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                if not stat.S_ISDIR(os.fstat(pfd).st_mode):
                    access &= ~((1 << 3) | sum(1 << n for n in range(4, 14)))
                rule = PathRule(access, pfd)
                checked(LIBC.syscall(445, fd, 1, ctypes.byref(rule), 0), 'Landlock path rule')
            finally:
                os.close(pfd)
        checked(LIBC.prctl(38, 1, 0, 0, 0), 'no_new_privs')
        checked(LIBC.syscall(446, fd, 0), 'Landlock restrict')
    finally:
        os.close(fd)
    sec = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    class Compare(ctypes.Structure):
        _fields_=[('arg',ctypes.c_uint),('op',ctypes.c_int),('a',ctypes.c_uint64),('b',ctypes.c_uint64)]
    sec.seccomp_rule_add_array.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint,ctypes.POINTER(Compare)]
    context = sec.seccomp_init(0x7fff0000)
    if not context:
        raise RuntimeError('seccomp is required')
    try:
        denied = ['connect',
                     'ptrace', 'process_vm_readv', 'process_vm_writev', 'pidfd_getfd',
                     'mount', 'umount2', 'setns', 'unshare', 'bpf', 'perf_event_open',
                     'open_by_handle_at', 'name_to_handle_at', 'truncate', 'truncate64',
                     'io_uring_setup', 'keyctl', 'add_key', 'request_key', 'kill', 'pidfd_send_signal']
        if local_socket_server:
            # LibreOffice needs a local listening pipe. Outgoing connect remains
            # denied, and only AF_UNIX socket creation is admitted.
            comparison=Compare(0,1,1,0)  # SCMP_CMP_NE, AF_UNIX
            checked(sec.seccomp_rule_add_array(context,0x50000|errno.EPERM,sec.seccomp_syscall_resolve_name(b'socket'),1,ctypes.byref(comparison)),'Unix socket restriction')
        else:denied += ['socket','bind','listen','accept','accept4']
        for name in denied:
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0:
                checked(sec.seccomp_rule_add(context, 0x50000 | errno.EPERM, number, 0), 'seccomp rule')
        checked(sec.seccomp_load(context), 'seccomp load')
    finally:
        sec.seccomp_release(context)
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        os.environ.pop(key, None)
    os.environ['HOME'] = str(root)
    os.chdir(root)

def bwrap_entry(argv):
    if argv == ['--help']:
        print('PPTX Landlock/seccomp adapter: --as-pid-1 --perms --argv0 --ro-bind-fd')
        return
    inner = argv[argv.index('--') + 1:]
    if '--apply-seccomp-then-exec' not in inner:
        raise ValueError('Unsupported sandbox invocation')
    import json
    profile = json.loads(inner[inner.index('--permission-profile') + 1])
    fs = profile.get('file_system', {})
    if profile.get('network') != 'restricted' or fs.get('type') != 'restricted':
        raise ValueError('Only restricted filesystem and network policies are supported')
    cwd = Path(inner[inner.index('--command-cwd') + 1]).resolve(strict=True)
    candidates=[cwd]
    if '--sandbox-policy-cwd' in inner:candidates.append(Path(inner[inner.index('--sandbox-policy-cwd')+1]).resolve())
    candidates += [Path(e['path']['path']).resolve() for e in fs['entries'] if e['path']['type']=='path']
    roots={p for target in candidates for p in [target,*target.parents] if p.parent==Path('/tmp') and p.name.startswith(('pptx-lab-job-','pptx-lab-resume-'))}
    root=next(iter(roots)) if len(roots)==1 else None
    if root is None:
        raise ValueError('Only PPTX task workspaces are supported: '+str(cwd)+'; profile='+str(fs))
    reads = []
    # Codex adds its exact executor/helper binaries as trusted mounts separately
    # from the requested filesystem profile. Keep those executable read grants.
    for index,arg in enumerate(argv[:argv.index('--')]):
        if arg=='--ro-bind' and index+2<len(argv) and argv[index+1]==argv[index+2]:
            path=Path(argv[index+1]).resolve()
            if str(path) not in ('/','/tmp','/root','/proc'):
                reads.append(str(path))
    for entry in fs['entries']:
        path = entry['path']
        if path['type'] != 'path':
            continue
        target = Path(path['path']).resolve()
        if entry['access'] == 'write' and not target.is_relative_to(root):
            raise ValueError('Write grant outside task')
        if entry['access'] == 'read':
            reads.append(str(target))
    command = inner[inner.index('--') + 1:]
    restrict(root, reads)
    os.chdir(cwd)
    os.execvpe(command[0], command, os.environ)

if __name__ == '__main__':
    import sys
    bwrap_entry(sys.argv[1:])
