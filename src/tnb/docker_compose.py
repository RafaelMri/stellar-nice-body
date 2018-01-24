import json
import jinja2  # noqa
import random
from pprint import pprint  # noqa

from .builder import (
    Builder,
    flatten_items,
)
from .util import (
    format_db_url,
    format_base_path,
)


class DockerCompose:
    builder = None
    quorums = None

    default_policies = dict(
        restart='always',
        force_scp=False,
        new_network=False,
        unsafe_quorum=False,
        print_config=False,
    )
    default_ports = dict(
        http=11626,
        peer=11625,
    )

    port_pool_by_instance = None

    @classmethod
    def from_quorum_json(cls, design, quorums_json):
        m = cls(design)

        m.quorums = json.loads(quorums_json)

        return m

    def __init__(self, design):
        self.design = design
        self.builder = Builder(design)
        self.port_pool_by_instance = dict()

    def make(self):
        if self.quorums is None:
            self.quorums = self.builder.make_quorums()

        return self.quorums

    def build(self, template_directories=None, default_policies=None):
        quorums_by_instances = dict()
        for _, quorum in self.quorums.items():
            quorums_by_instances.setdefault(quorum['instance'], list())
            quorums_by_instances[quorum['instance']].append(quorum)

        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_directories),
        )
        nodes_template = jinja_env.get_template('nodes.yml')
        cfg_template = jinja_env.get_template('stellar-core-config.cfg')

        nodes_files = dict()
        cfg_files = dict()
        for instance_name, quorums in quorums_by_instances.items():
            cfg_files.setdefault(instance_name, dict())
            nodes = list()
            for quorum in quorums:
                data = self.serialize_node_quorum(quorum, default_policies)

                cfg_files[instance_name][quorum['node']] = cfg_template.render(node=data)
                nodes.append(data)

            nodes_files[instance_name] = nodes_template.render(instance_name=instance_name, nodes=nodes)

        return dict(
            nodes=nodes_files,
            cfgs=cfg_files,
        )

    def serialize_node_quorum(self, quorum, default_policies=None):
        policies = self.default_policies.copy()
        if default_policies:
            policies.update(default_policies)

        instance = self.builder.instances.get(quorum['instance'])
        node = self.builder.nodes.get(quorum['node'])
        node_data = policies.copy()
        node_data.update(node.serialize())

        validators = list()
        node_names = list()
        known_peers = list()
        vs = flatten_items(quorum['validators'])
        for v, n in self.builder.nodes.nodes.items():
            if node.name == v:
                continue

            node_names.append(dict(
                hostname=n.hostname,
                public_address=n.public_address,
            ))
            known_peers.append(dict(
                hostname=n.hostname,
                peer_port=self.get_port_pair(v)['peer_port'],
            ))

            if v in vs:
                if v not in validators:
                    validators.append(v)

        if node.is_validator:
            validators.append('self')

        node_data['extra_settings'] = self.builder.network.default_settings
        node_data['validators'] = validators
        node_data['node_names'] = node_names
        node_data['known_peers'] = known_peers
        node_data['db_url'] = format_db_url(
            dbname=node_data['safe_name'],
            **self.builder.databases.get(node.database).serialize()
        )
        node_data['network_passphrase'] = self.builder.network.passphrase
        node_data['base_path'] = format_base_path(base_path=instance.base_path, **node_data)

        ports = self.get_port_pair(node.name)
        node_data['http_port'] = ports['http_port']
        node_data['peer_port'] = ports['peer_port']

        history = self.builder.history.get(node.history)
        node_data['default_history'] = dict(
            name=node.history,
            getter=history.getter.format(**node_data),
            putter=history.putter.format(**node_data),
        )
        node_data['extra_historiess'] = self.builder.history.get_trusted_histories(self.builder.nodes)

        return node_data

    port_range = list(range(11000, 12000))

    def get_port_pair(self, name):
        node = self.builder.nodes.get(name)
        instance = self.builder.instances.get_instance_by_node(name)

        if node.http_port:
            http_port = node.http_port
        else:
            http_port = self.get_port_by_instance('http', instance.name, name)

        if node.peer_port:
            peer_port = node.peer_port
        else:
            peer_port = self.get_port_by_instance('peer', instance.name, name)

        return dict(
            http_port=http_port,
            peer_port=peer_port,
        )

    def get_port_by_instance(self, kind, instance_name, name):
        self.port_pool_by_instance.setdefault(instance_name, dict())
        self.port_pool_by_instance[instance_name].setdefault(kind, dict())

        if name not in self.port_pool_by_instance[instance_name][kind]:
            if len(self.port_pool_by_instance[instance_name][kind]) < 1:
                port = self.default_ports[kind]
            else:
                while True:
                    port = random.sample(self.port_range, 1)[0]
                    if port not in self.port_pool_by_instance[instance_name][kind]:
                        break

            self.port_pool_by_instance[instance_name][kind][name] = port

        return self.port_pool_by_instance[instance_name][kind][name]
