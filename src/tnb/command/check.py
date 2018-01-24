import logging

from ..validator import Validator
from ..util import print_error
from ..exceptions import ValidationError


log = logging.getLogger(__name__)


def subparser(subparser):
    parser = subparser.add_parser(
        'check',
        help='check the design',
    )
    parser.set_defaults(command='check')

    return


def run(parser, args):
    try:
        Validator(args.design).validate()
    except ValidationError as e:
        print_error('found problems: %s' % e)

        return 1
    else:
        print('OK')

    return 0
