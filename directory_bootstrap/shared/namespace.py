# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

import errno
import os
from ctypes import CDLL, c_char_p, c_int, cast, get_errno

_CLONE_NEWNS = 0x00020000
_CLONE_NEWUTS = 0x04000000

_lib_c = CDLL("libc.so.6", use_errno=True)


def unshare_current_process(messenger):
    messenger.info('Unsharing Linux namespaces (mount, UTS/hostname)...')
    ret = _lib_c.unshare(c_int(_CLONE_NEWNS | _CLONE_NEWUTS))
    if ret:
        _errno = get_errno() or errno.EPERM
        raise OSError(_errno, 'Unsharing Linux namespaces failed: ' + os.strerror(_errno))


def set_hostname(hostname):
    hostname_char_p = cast(hostname, c_char_p)
    hostname_len_size_t = _lib_c.strlen(hostname_char_p)
    ret = _lib_c.sethostname(hostname_char_p, hostname_len_size_t)
    if ret:
        _errno = get_errno() or errno.EPERM
        raise OSError(_errno, 'Setting hostname failed: ' + os.strerror(_errno))
