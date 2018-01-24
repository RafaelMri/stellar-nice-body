import logging
import os
import datetime
import socket
import copy

from stellar_base.keypair import Keypair

from ..design import Node


log = logging.getLogger(__name__)


def subparser(subparser):
    parser = subparser.add_parser(
        'fix-design',
        help='fix the incorrect design',
    )
    parser.set_defaults(command='fix_design')

    return


def run(parser, args):
    nodes = copy.deepcopy(args.design.design_yaml['nodes'])
    for k, v in nodes.items():
        if v is None:
            v = Node.get_defaults_design()
        elif 'secret_seed' not in v:
            v['secret_seed'] = Keypair.random().seed().decode()

        args.design.design_yaml['nodes'][k] = v

    print('''%(sep)s
# generated at %(date)s from '%(user)s@%(hostname)s'
%(content)s''' % dict(
        sep='#' * 80,
        date=datetime.datetime.now().isoformat(),
        user=os.environ.get('USER'),
        hostname=socket.gethostname(),
        content=args.design.serialize(),
    ))

    return 0
