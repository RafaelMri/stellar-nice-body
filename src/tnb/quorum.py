##################################################################
#    Copyright 2008 Spike^ekipS <spikeekips@gmail.com>
#
#       This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
##################################################################

'''
# rule to compose quorums with regions

## facts

* there are 2 or more regions
* each region has validators
* the validators in the same region share the quorum configuration

## how to compose

* choose one region
* how to compose quroum of 2 regions
    - find nearest one, generate available commons
    - choose one common, which has highest liveness and safety
    - merge common with the initial validators
    - find second nearest one, generate available commons with the meged
    - among available commons, choose one with the previous same rule
    - and which has least shared in commons
* choose next region, which is not composed with the others
'''


import argparse
import itertools
import logging
import colorlog
import sys
import random  # noqa
from pprint import pprint, pformat  # noqa
import termcolor
import tabulate


IS_TERM = sys.stdout.isatty()

log = logging.getLogger(__name__)


class AvailableQuorumCommons:
    ra = None
    rb = None
    failure = None

    commons = None

    def __init__(self, name, ra, rb, failure):
        self.name = name
        self.ra = ra
        self.rb = rb
        self.failure = failure
        self.min_size = 3 * self.failure + 1

        self.nn = set(self.ra) | set(self.rb)

    def make(self):
        C = list(set(self.ra) & set(self.rb))

        # min size
        passed = len(self.ra) - self.min_size >= 0
        if passed:
            passed = len(self.rb) - self.min_size >= 0

        # liveness
        if passed:
            passed = len(self.nn) - len(C) - self.failure >= 0
        if passed:
            passed = len(self.nn) - len(C) - self.failure >= 0

        # safety
        if passed:
            passed = 2 * len(C) - len(self.nn) - 1 - self.failure >= 0
        if passed:
            passed = 2 * len(C) - len(self.nn) - 1 - self.failure >= 0

        if self.commons is None:
            self.commons = dict()

        if passed:
            self.commons['commons_safety'] = C

        return self.commons_safety

    def reset(self):
        self.commons = None

        return

    def cache(f):
        def w(self, *a, **kw):
            if self.commons is None:
                self.commons = dict()

            if f.__name__ not in self.commons:
                self.commons[f.__name__] = f(self, *a, **kw)

            return self.commons[f.__name__]

        return w

    @property
    @cache
    def commons_min_size(self):
        self.log_debug('trying to get commons for satisfy the minimum size with failure: `vn >= min_size`: %d %d')

        C = set(self.ra) & set(self.rb)

        n = 0
        for c in self.chain(self.ra, self.rb):
            if len(C) > 0 and len(C & set(c)) < len(C):
                continue

            vnra = self.combine_quorum_and_common(self.ra, c)
            vnrb = self.combine_quorum_and_common(self.rb, c)

            vra = vnra - self.min_size
            vrb = vnrb - self.min_size
            failed = dict()
            failed['vnra'] = vra >= 0
            failed['vnrb'] = vrb >= 0

            logs = list()
            for k, v in failed.items():
                logs.append(
                    '%s(%d >= %d=%s)' % (
                        k,
                        vnra if k == 'vnra' else vnrb,
                        self.min_size,
                        colored('%-5s' % v, 'green' if v else 'red'),
                    ),
                )

            self.log_debug(
                'min size - is valid: %s check: %s common: %s',
                colored('%-5s' % (False not in failed.values()), 'green' if False not in failed.values() else 'red'),
                ', '.join(logs),
                c,
            )
            if False in failed.values():
                continue

            n += 1
            yield (c, dict(min_size=(vra, vrb)))

        if n > 0:
            self.log_debug('%d commons for satisfy the minimum size with failure', n)
        else:
            self.log_error('minimum size pairs not found')

    @property
    @cache
    def commons_liveness(self):
        self.log_debug('trying to get the commons for keep the liveness: `vn - cn >= f`')

        n = 0
        for q, value in sorted(self.commons_min_size, key=lambda x: len(x), reverse=True):
            # vnra = self.combine_quorum_and_common(self.ra, q)
            # vnrb = self.combine_quorum_and_common(self.rb, q)
            cn = len(q)

            failed = dict()

            vra = len(self.nn) - cn - self.failure
            vrb = len(self.nn) - cn - self.failure
            failed['vnra'] = vra >= 0
            failed['vnrb'] = vrb >= 0

            logs = list()
            for k, v in failed.items():
                logs.append(
                    '%s(%d - %d = %d >= %d)' % (
                        k,
                        # vnra if k == 'vnra' else vnrb,
                        len(self.nn),
                        cn,
                        # vra if k == 'vnra' else vrb,
                        len(self.nn),
                        self.failure,
                    ),
                )

            self.log_debug(
                'liveness - is valid: %s check: %s common: %s',
                colored('%-5s' % (False not in failed.values()), 'green' if False not in failed.values() else 'red'),
                ', '.join(logs),
                q,
            )

            if False in failed.values():
                continue

            value['liveness'] = (vra, vrb)
            n += 1
            yield (q, value)

        if n > 0:
            self.log_debug('%d commons for keep the liveness', n)
        else:
            self.log_error('liveness pairs not found')

    @property
    @cache
    def commons_safety(self):
        self.log_debug('trying to get the commons for filling the safety numbers: `2*cn - vn - 1 >= f`')

        n = 0
        for q, value in sorted(self.commons_liveness, key=lambda x: len(x), reverse=True):
            # vnra = self.combine_quorum_and_common(self.ra, q)
            # vnrb = self.combine_quorum_and_common(self.rb, q)
            cn = len(q)

            failed = dict()
            vra = 2 * cn - len(self.nn) - 1 - self.failure
            vrb = 2 * cn - len(self.nn) - 1 - self.failure
            failed['vnra'] = vra >= 0
            failed['vnrb'] = vrb >= 0

            logs = list()
            for k, v in failed.items():
                logs.append(
                    '%s(2 * %d - %d - 1 = %d >= %d)' % (
                        k,
                        cn,
                        # vnra if k == 'vnra' else vnrb,
                        len(self.nn),
                        # 2 * cn - (vnra if k == 'vnra' else vnrb) - 1,
                        2 * cn - len(self.nn) - 1,
                        self.failure,
                    )
                )
            self.log_debug(
                'safety - is valid: %s check: %s common: %s',
                colored('%-5s' % (False not in failed.values()), 'green' if False not in failed.values() else 'red'),
                ', '.join(logs),
                q,
            )

            if False in failed.values():
                continue

            value['safety'] = (vra, vrb)
            n += 1
            yield (q, value)

        if n > 0:
            self.log_debug('%d commons for filling the safety numbers', n)
        else:
            self.log_error('safety pairs not found')

    def combine_quorum_and_common(self, q, c):
        return len(set(q) | set(c))

    def print_set(self, name, q, c):
        m = 100

        co = sorted(c)
        e = sorted(set(q) - set(c))
        n = sorted(set(c) - set(q))
        v = sorted(set(q) | set(c))

        vs = ', '.join(map(lambda x: colored(x, 'green') if x in c else colored(x, 'yellow'), v))
        rows = (
            ('quroum', name + ('' if len(name) > m else ' ' * (m - len(name))) + '.'),
            ('validators', '%d: %s' % (len(v), vs)),
            ('extra', ', '.join(map(lambda x: colored(x, 'yellow'), e))),
            ('newly added', ', '.join(map(lambda x: colored(x, 'magenta'), n))),
            ('safety?', '%s: 2 * %d - %d - 1 = %s' % (
                colored('2 * cn - vn - 1 >= f', 'magenta'),
                len(co),
                len(v),
                colored('%d >= %d' % (2 * len(co) - len(v) - 1, self.failure), 'green'),
            )),
            ('liveness?', '%s: %d - %d = %s' % (
                colored('vn - cn >= f', 'magenta'),
                len(v),
                len(co),
                colored('%d >= %d' % (len(v) - len(co), self.failure), 'green'),
            )),
        )

        return tabulate.tabulate(rows, tablefmt='fancy_grid')

    def log_debug(self, msg, *a, **kw):
        log.debug('[%s] %s' % (self.name, msg), *a, **kw)
        return

    def log_error(self, msg, *a, **kw):
        log.error('[%s] %s' % (self.name, msg), *a, **kw)
        return

    def chain_expensive(self, a, b):
        self.log_debug('trying to create chains: %d <-> %d', len(a), len(b))

        l = sorted(set(a) | set(b))
        k = list(map(lambda x: [x], l))
        while len(k[-1]) < len(l):
            for i in k[:]:
                for j in l:
                    if j in i:
                        continue

                    y = sorted(i + [j])
                    if y in k:
                        continue

                    k.append(y)
                    yield y

    def chain(self, a, b):
        self.log_debug('trying to create chains: %d <-> %d', len(a), len(b))

        size = 6
        la = self.make_restricted_pair(a, size)
        lb = self.make_restricted_pair(b, size)
        for i in range(len(la) + len(lb)):
            for j in itertools.combinations(la + lb, i):
                yield list(itertools.chain(*j))

    def make_restricted_pair(self, a, size):
        if len(a) < size:
            return list(map(lambda x: [x], a))

        k = len(a)
        j = 1
        while True:
            m = int(len(a) / j)
            n = len(a) % j

            k = m + n
            if k <= size:
                break

            j += 1

        l = list()
        for i in range(0, m * j, j):
            l.append(a[i:i + j])

        l.extend(map(lambda x: [x], a[m * j:]))

        return l


class RegionalQuorum:
    regions = None
    failure = None
    number_of_near_regions = None

    def __init__(self, regions, failure, number_of_near_regions=None):
        assert type(regions) in (dict,)

        self.regions = regions
        self.failure = failure
        if number_of_near_regions is None:
            number_of_near_regions = 2

        self.number_of_near_regions = number_of_near_regions

    def compose(self, distances):
        connected = dict()
        quorums = dict()
        rs = sorted(self.regions.keys())

        for i in range(len(rs)):
            for level in range(self.number_of_near_regions)[:len(distances[rs[i]])]:
                near = random.sample(distances[rs[i]][level][1], 1)[0]
                key = tuple(sorted((rs[i], near)))
                if key in connected:
                    continue

                if rs[i] in quorums:
                    ra = quorums[rs[i]]
                else:
                    ra = self.regions[rs[i]]

                if near in quorums:
                    rb = quorums[near]
                else:
                    rb = self.regions[near]

                cs = self.compose_pair(key, ra, rb)
                if cs is None:
                    log.error('failed to compose quorums for %s', key)
                    return None

                connected[key] = True
                quorums[rs[i]] = cs[0]
                quorums[near] = cs[1]

        return quorums

    def compose_pair(self, name, ra, rb):
        qc = AvailableQuorumCommons(name, ra, rb, self.failure)
        commons = qc.make()

        # choose best one
        l = sorted(
            commons,
            key=lambda x: (
                sum(x[1]['safety']),
                len(set(ra) & set(x[0])),
                sum(x[1]['liveness']),
            ),
        )

        if len(l) < 1:
            log.error('commons not found: %s', name)
            return

        log.debug('1 common was selected: %s', l[0])

        t = l[0][0]  # choose minimum

        return (
            sorted(set(ra) | set(t)),
            sorted(set(rb) | set(t)),
        )


def colored(s, *a, **kw):
    if IS_TERM:
        return termcolor.colored(s, *a, **kw)

    return s


def print_quorum(name, q, quorums, initial, failure):
    connected = list()
    commons = set()
    for r, v in quorums.items():
        if r == name:
            continue

        c = set(q) & set(v)
        if len(c) < 1:
            continue

        commons = commons | set(c)
        connected.append(dict(
            name=r,
            commons=c,
            liveness=(
                (
                    '%d - %d = %d >= %d' % (len(q), len(c), len(q) - len(c), failure),
                    len(q) - len(c) >= failure,
                ),
                (
                    '%d - %d = %d >= %d' % (len(v), len(c), len(v) - len(c), failure),
                    len(v) - len(c) >= failure,
                ),
            ),
            safety=(
                (
                    '2 * %d - %d - 1 = %d >= %d' % (len(c), len(q), 2 * len(c) - len(q) - 1, failure),
                    2 * len(c) - len(q) - 1 >= failure,
                ),
                (
                    '2 * %d - %d - 1 = %d >= %d' % (len(c), len(v), 2 * len(c) - len(v) - 1, failure),
                    2 * len(c) - len(v) - 1 >= failure,
                ),
            ),
        ))

    extra = sorted(set(initial) - set(commons))

    rows = [
        ('name', name, ''),
        ('validators', ', '.join(q), len(q)),
        ('commons(superset)', ', '.join(commons), len(commons)),
        ('extra', ', '.join(extra), len(extra)),
    ]
    for c in connected:
        rows.append(('* connected with "%s"' % c['name'], '', ''))
        rows.append(('>   commons', ', '.join(c['commons']), ''))
        rows.append((
            '>   liveness(%s)' % name,
            c['liveness'][0][0],
            colored(c['liveness'][0][1], 'green' if c['liveness'][0][1] else 'red'),
        ))
        rows.append((
            '>   liveness(%s)' % c['name'],
            c['liveness'][1][0],
            colored(c['liveness'][1][1], 'green' if c['liveness'][1][1] else 'red'),
        ))
        rows.append((
            '>   safety(%s)' % name,
            c['safety'][0][0],
            colored(c['safety'][0][1], 'green' if c['safety'][0][1] else 'red'),
        ))
        rows.append((
            '>   safety(%s)' % c['name'],
            c['safety'][1][0],
            colored(c['safety'][1][1], 'green' if c['safety'][1][1] else 'red'),
        ))

    return tabulate.tabulate(rows, tablefmt=('fancy_grid' if IS_TERM else 'grid'))


if __name__ == '__main__':
    tabulate.PRESERVE_WHITESPACE = True

    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)s - %(message)s',
            reset=True,
            log_colors={
                # 'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
        ),
    )

    log.addHandler(handler)

    log.debug('nice body started')

    parser = argparse.ArgumentParser()
    parser.add_argument('-verbose', action='store_true')
    parser.add_argument('-near', type=int, default=2, help='number of near regions to be connected to each region')
    parser.add_argument('F', type=int, default=0, help='number of failure')
    parser.add_argument('NR', nargs='+', type=int, help='number of validators in each region')

    options = parser.parse_args()

    if options.verbose:
        logging.root.setLevel(logging.DEBUG)

    log.debug('options: %s', pformat(options.__dict__))

    if options.F < 1:
        log.warning('`F`, the number of failure is %s, it is too low.', options.F)

    if options.near >= len(options.NR):
        log.warning('`-near` is too high, will be reset below to the number of regions, "%d"', len(options.NR) - 1)
        options.near = len(options.NR) - 1

    min_size = 3 * options.F + 1
    log.debug('constraints: failure=%d min_size=%d', options.F, min_size)

    node_name_format = 'r%%s-%%0%dd' % (max(map(lambda x: len(str(x)), options.NR)) + 1)

    nr = dict()
    for r, i in enumerate(options.NR):
        nr['r%d' % r] = list(map(lambda x: node_name_format % (r, x), range(i)))

    log.debug('''created the primitive quorums:
%s''', '\n'.join(map(lambda x: '* %s: %s' % (x[0], ', '.join(x[1])), nr.items())))

    # make distances
    s = sorted(nr.keys())

    distances = dict()
    for i in range(len(s)):
        distances[s[i]] = list(map(
            lambda x: (x[0] / 10, (x[1],)),
            enumerate(s[i + 1:] + s[:len(s) - len(s[i:])]),
        ))

    quorums = RegionalQuorum(nr, options.F, options.near).compose(distances)
    if quorums is None:
        print('failed to compose quourms')
        sys.exit(1)

    for r, v in quorums.items():
        print(print_quorum(r, v, quorums, nr[r], options.F))

    sys.exit(0)
