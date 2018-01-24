import itertools
import re
import sys
import pathlib
import colorful


def calculate_tags_distance(a, b):
    r0 = a[0]
    r1 = b[0]
    if r0 == r1:
        return _calculate_tags_distance(a[1:], b[1:]) / 10

    d = abs((r0 - r1))
    if d > 5:
        d = 10 - r1 + r0

    return d / 10


def _calculate_tags_distance(a, b):
    l = list(itertools.zip_longest(a, b))
    index = 0
    for index, b in enumerate(map(lambda x: x[0] == x[1], l)):
        if b is False:
            break

    if len(l) < 1:
        return 0

    return 1 - index / len(l)


def get_distances_by_region(distances, region_name):
    ds = list()
    for key, ratio in distances.items():
        if region_name not in key:
            continue

        other = list(set(key) - set((region_name,)))[0]
        ds.append((other, ratio))

    d = list()
    for key, groups in itertools.groupby(ds, key=lambda x: x[1]):
        d.append((key, list(map(lambda x: x[0], groups))))

    return sorted(d)


RE_BLANK = re.compile('[\s]+')


def safe_name(n):
    return RE_BLANK.sub('__', n.replace('-', '_'))


def format_db_url(**data):
    return 'postgresql://dbname={dbname} user={user} password={password} host={host} port={port}'.format(**data)


def format_base_path(**data):
    return str(pathlib.Path('{base_path}/{safe_name}'.format(**data)).joinpath())


def print_error(s, *a, **kw):
    print(colorful.red('[error]'), end=' ', file=sys.stderr)  # noqa
    print(s, *a, **kw, file=sys.stderr)

    return


def print_parser_error(parser, s, *a, **kw):
    print(colorful.red('[error]'), end=' ', file=sys.stderr)  # noqa
    parser.error(s, *a, **kw)

    return
