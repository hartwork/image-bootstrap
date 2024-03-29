# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later



import re

_year = '([2-9][0-9]{3})'
_month = '(0[1-9]|1[0-2])'
_day = '(0[1-9]|[12][0-9]|3[01])'
_time = '(T[0-9]{6}Z)?'

_STAGE3_TARBALL_DATE_PATTERN = '^(?P<date>%s%s%s%s)/stage3-(?P<arch>[^ -]+)(?P<flavor>-openrc)?-[0-9]+(T[0-9]+Z)?\\.tar\\.[^ ]+ [1-9]+[0-9]*$' % (_year, _month, _day, _time)
_stage3_tarball_date_matcher = re.compile(_STAGE3_TARBALL_DATE_PATTERN)


def find_latest_stage3_date(stage3_latest_file_content, stage3_latest_file_url, architecture):
    matches = []
    for line in stage3_latest_file_content.split('\n'):
        m = _stage3_tarball_date_matcher.match(line)
        if m is None:
            continue
        if m.group('arch') != architecture:
            continue
        matches.append(m)

    message = ('Content from %s does not seem to contain '
            'well-formed OpenRC/default '
            'stage3 tarball entr(y|ies)'
            % stage3_latest_file_url
            )

    if not matches:
        raise ValueError(message)

    m = sorted(matches, key=lambda e: e.group(1))[-1]  # i.e. most recent
    return (int(m.group(2)), int(m.group(3)), int(m.group(4))), m.group(5), m.group('flavor') or ''
