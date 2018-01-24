import logging
import jinja2  # noqa
import json
import socket
import os
import pathlib

from ..validator import Validator
from ..docker_compose import DockerCompose
from ..util import print_error
from ..exceptions import (
    ValidationError,
)

log = logging.getLogger(__name__)


def subparser(subparser):
    parser = subparser.add_parser(
        'make',
        help='generate runtime deployment files',
    )
    parser.set_defaults(command='make')

    parser.add_argument(
        '-quorums',
        help='set existing `quorums.json`',
    )

    parser.add_argument(
        '-template',
        help='set template directory',
    )

    parser.add_argument(
        '-not-flat',
        action='store_true',
    )
    # parser.add_argument(
    #     '-output',
    #     help='set output directory',
    # )

    return


# default template directories
default_template_directories = (
    pathlib.Path(__file__).parent.joinpath('../../..').absolute().joinpath('template'),
    pathlib.Path('.').absolute().joinpath('template'),
)


def run(parser, args):
    try:
        Validator(args.design).validate()
    except ValidationError as e:
        print_error('found problems: %s' % e)

        return 1

    if args.quorums:
        args.quorums = pathlib.Path(args.quorums).read_text()

    if args.quorums:
        dc = DockerCompose.from_quorum_json(args.design, args.quorums)
    else:
        dc = DockerCompose(args.design)

    if args.template:
        template_directory = pathlib.Path(args.template).absolute()
    else:
        template_directory = pathlib.Path('.').joinpath('template').absolute()

    dc.make()

    template_directories = list(default_template_directories) + [template_directory]
    files_force_scp = dc.build(template_directories=template_directories, default_policies=dict(force_scp=True, restart='no'))
    files_new_network = dc.build(template_directories=template_directories, default_policies=dict(new_network=True, restart='no'))
    files_normal = dc.build(template_directories=template_directories, default_policies=dict(force_scp=False))

    save_directory = args.save_directory.joinpath(args.now.strftime('%Y%m%d%H%M%S'))
    save_directory.mkdir(parents=True, exist_ok=False)

    generate_cfg_file(args, files_force_scp['cfgs'], save_directory.joinpath('config'), flat=not args.not_flat)

    generate_docker_compose(args, files_force_scp['nodes'], save_directory.joinpath('docker-compose'), flat=not args.not_flat, kind='forcescp')
    generate_docker_compose(args, files_new_network['nodes'], save_directory.joinpath('docker-compose'), flat=not args.not_flat, kind='new_network')
    generate_docker_compose(args, files_normal['nodes'], save_directory.joinpath('docker-compose'), flat=not args.not_flat, kind='normal')

    # save design files
    mcontent = '''%(sep)s
# generated at %(date)s from '%(user)s@%(hostname)s'
%(content)s''' % dict(
        sep='#' * 80,
        date=args.now.isoformat(),
        user=os.environ.get('USER'),
        hostname=socket.gethostname(),
        content=args.design.serialize(),
    )

    save_directory.joinpath('design.yml').write_text(mcontent)

    # save quorum files
    save_directory.joinpath('quorums.json').write_text(json.dumps(dc.quorums, indent=2))

    print('successfully saved to ', save_directory.as_uri())

    dc.builder.make_quorums_graph(
        dc.quorums,
        output=save_directory.joinpath('quorums'),
        output_format='png',
    )
    dc.builder.make_quorum_validators_graph(
        dc.quorums,
        output=save_directory.joinpath('validators'),
        output_format='png',
    )
    dc.builder.make_quorum_validators_direct_graph(
        dc.quorums,
        output=save_directory.joinpath('validators-direct'),
        output_format='png',
    )

    return 0


def generate_docker_compose(args, files, dc_directory, kind, flat=False):
    dc_directory.mkdir(parents=True, exist_ok=True)

    m = dict(
        date=args.now.isoformat(),
        user=os.environ.get('USER'),
        hostname=socket.gethostname(),
    )

    for instance_name, content in files.items():
        mm = m.copy()
        mm.update(content=content.strip())
        mcontent = '''# generated at %(date)s from '%(user)s@%(hostname)s'
%(content)s''' % mm

        if flat:
            instance_directory = dc_directory
        else:
            instance_directory = dc_directory.joinpath(kind).joinpath(instance_name)

        instance_directory.mkdir(parents=True, exist_ok=True)

        filename = 'docker-compose.yml'
        if flat:
            filename = '%(kind)s-%(instance)s.yml' % dict(kind=kind, instance=instance_name)

        f = instance_directory.joinpath(filename)
        f.write_text(mcontent)

    return


def generate_cfg_file(args, files, dc_directory, flat=False):
    dc_directory.mkdir(parents=True, exist_ok=True)

    m = dict(
        date=args.now.isoformat(),
        user=os.environ.get('USER'),
        hostname=socket.gethostname(),
    )

    for instance_name, v in files.items():
        for node_name, content in v.items():
            mm = m.copy()
            mm.update(content=content.strip())
            mcontent = '''# generated at %(date)s from '%(user)s@%(hostname)s'
%(content)s''' % mm

            if flat:
                instance_directory = dc_directory
            else:
                instance_directory = dc_directory.joinpath(instance_name)

            instance_directory.mkdir(parents=True, exist_ok=True)

            fargs = dict(node=node_name, instance='')
            if flat:
                fargs.update(instance=instance_name)

            filename = '%(instance)s-%(node)s.cfg' % fargs
            f = instance_directory.joinpath(filename)
            f.write_text(mcontent)

    return
