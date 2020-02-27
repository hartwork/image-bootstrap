# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import os
import subprocess
import sys


_WANTED_PATHS = (
    '/usr/local/sbin',
    '/usr/local/bin',
    '/usr/sbin',
    '/usr/bin',
    '/sbin',
    '/bin',
)


def _insert_before_after(list_, befores, element, afters, strict=False):
    """
    Insert somewhere after certain elements but also before certain others.

    >>> list_ = [2, 0, 0, 1, 0, 0, 5, 6, 0]
    >>> _insert_before_after(list_, [1, 2], 3, [5, 6])
    >>> list_
    [2, 0, 0, 1, 3, 0, 0, 5, 6, 0]
    """
    def or_default(func, arg, default):
        try:
            return func(arg)
        except ValueError:
            return default

    max_before_index = or_default(
        max, (or_default(list_.index, e, -1) for e in befores),
        -1)

    min_afters_index = or_default(
        min, (or_default(list_.index, e, len(list_)) for e in afters),
        len(list_))

    if max_before_index >= min_afters_index:
        if strict:
            raise Exception('Cannot satisfy "befores" and "after"'
                            ' at the same time'
                            ' with this particular list')
        else:
            insertion_index = len(list_)
    else:
        insertion_index = max_before_index + 1

    list_.insert(insertion_index, element)


def _sanitize_path(path):
    """
    Arch has a rather short $PATH:
    ```
    # env -i bash -c 'sed "s,:,\n,g" <<<"$PATH"'
    /usr/local/sbin
    /usr/local/bin
    /usr/bin
    ```

    With their symlinks it makes sense:
    ```
    # ls -l /bin /sbin /usr/sbin
    lrwxrwxrwx 1 root root 7 Oct 17 07:32 /bin -> usr/bin
    lrwxrwxrwx 1 root root 7 Oct 17 07:32 /sbin -> usr/bin
    lrwxrwxrwx 1 root root 3 Oct 17 07:32 /usr/sbin -> bin
    ```

    Now if we call chroot on Arch, that short $PATH is used
    in a distro made for /usr/sbin to be in $PATH.  Hence
    we put it in ourselves.

    https://github.com/hartwork/image-bootstrap/issues/62
    """

    future_paths = path.split(os.pathsep)

    tasks = [(_WANTED_PATHS[:i], wanted_path, _WANTED_PATHS[i + 1:])
             for i, wanted_path in enumerate(_WANTED_PATHS)]

    for befores, element, afters in tasks:
        if element in future_paths:
            continue

        _insert_before_after(future_paths, befores, element, afters)

    return os.pathsep.join(future_paths)


def sanitize_path(env=None):
    if env is None:
        env = os.environ

    env['PATH'] = _sanitize_path(env['PATH'])


class Executor(object):
    def __init__(self, messenger, stdout=None, stderr=None):
        self._messenger = messenger
        self._announce_target = stdout or sys.stdout
        self._default_stdout = stdout or sys.stdout
        self._default_stderr = stderr or sys.stderr

    def check_call(self, argv, env=None, cwd=None):
        self._messenger.announce_command(argv)
        subprocess.check_call(argv,
                stdout=self._default_stdout,
                stderr=self._default_stderr,
                env=env,
                cwd=cwd,
                )

    def check_output(self, argv):
        self._messenger.announce_command(argv)
        return subprocess.check_output(argv, stderr=self._default_stderr)
