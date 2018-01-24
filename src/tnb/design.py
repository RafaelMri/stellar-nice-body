import yaml
import io
import ipaddress
from stellar_base.utils import DecodeError
from stellar_base.keypair import Keypair

from .util import (
    safe_name,
)
from .exceptions import (
    ValidationError,
)


class Design:
    design_yaml = None

    def serialize(self, format=None):
        if format is None:
            format = 'yaml'

        if format == 'yaml':
            return yaml.dump(self.design_yaml, default_flow_style=False, indent=4).strip()

    @classmethod
    def from_string(cls, f, **kw):
        return cls(yaml.load(io.BytesIO(f.encode('utf-8'))), **kw)

    def __init__(self, design_yaml):
        assert isinstance(design_yaml, dict)

        self.design_yaml = design_yaml


class ValidateTypeField:
    @classmethod
    def is_empty(cls, v):
        if v is None:
            return True

        if type(v) in (str,) and len(v.strip()) < 1:
            return True

        if type(v) in (list, tuple, dict) and len(v) < 1:
            return True

        return False

    @classmethod
    def validate_field(
            cls,
            k,
            data,
            allow_missing=False,
            allow_empty=False,
            value_types=None,
            check_func=None,
    ):
        if data is None or k not in data:
            if allow_missing:
                return

            raise ValidationError('`%s` is missing' % k)

        v = data[k]
        if v is None and not allow_empty:
            raise ValidationError('empty `%s`' % k)

        if value_types is not None and type(v) not in value_types:
            raise ValidationError('wrong `%s`, "%s": must be %s' % (k, v, value_types))

        if cls.is_empty(v):
            if not allow_empty:
                raise ValidationError('empty `%s`' % k)
        else:
            if check_func is not None:
                check_func(k, v, data)

        return


class Network(ValidateTypeField):
    defaults = dict(
        number_of_failure=1,
        number_of_connected_regions=3,
    )
    passphrase = None
    number_of_connected_regions = None
    default_settings = None

    def serialize(self, *a, **kw):
        return dict(
            passphrase=self.passphrase,
        )

    @classmethod
    def from_design(cls, design):
        m = cls()
        m.passphrase = design.design_yaml['network']['passphrase']
        m.number_of_connected_regions = design.design_yaml['network'].get(
            'number_of_connected_regions',
            cls.defaults['number_of_connected_regions'],
        )
        m.default_settings = design.design_yaml['network'].get(
            'default_settings',
            dict(),
        )
        if type(m.default_settings) not in (dict,):
            m.default_settings = dict()

        if 'failure_safety' not in m.default_settings:
            m.default_settings['failure_safety'] = -1

        m.number_of_failure = m.default_settings['failure_safety']
        if m.number_of_failure == -1:
            m.number_of_failure = 1

        if m.number_of_failure < 1:
            raise ValidationError('`number_of_failure` is too low: "%s"' % m.number_of_failure)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field('network', design_yaml, value_types=(dict,))

        network = design_yaml['network']
        cls.validate_field('passphrase', network, value_types=(str,))

        kw['validated'].append(cls.__name__)

        return


class Regions(ValidateTypeField):
    regions = None

    def serialize(self, *a, **kw):
        return dict(
            regions=dict(map(lambda x: (x[0], x[1].serialize()), self.regions.items())),
        )

    @classmethod
    def from_design(cls, design):
        m = cls()

        data = design.design_yaml['regions']
        for name in data.keys():
            m.regions[name] = Region.from_design(design, name)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field('regions', design_yaml, value_types=(dict,))

        for name in design_yaml['regions'].keys():
            Instance.validate_yaml(design_yaml, name, **kw.get('region', dict()))

        kw['validated'].append(cls.__name__)

        return

    def __init__(self):
        self.regions = dict()

    def get(self, name):
        return self.regions[name]

    def get_region_by_instance(self, name):
        for region in self.regions.values():
            if name in region.instances:
                return region

        return None


class Region(ValidateTypeField):
    name = None
    tags = None
    instances = None

    def serialize(self, *a, **kw):
        return dict(
            name=self.name,
            tags=self.tags,
            instances=self.instances,
        )

    @classmethod
    def from_design(cls, design, name):
        m = cls()

        data = design.design_yaml['regions'][name]

        m.name = name
        m.tags = data.get('tags', list())
        m.instances = data.get('instances', list())

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, instance_name):
        cls.validate_field(instance_name, design_yaml['regions'], value_types=(dict,))

        return

    def __init__(self):
        self.tags = list()
        self.instances = list()


class Instances(ValidateTypeField):
    instances = None

    def serialize(self, *a, **kw):
        return dict(
            instances=dict(map(lambda x: (x[0], x[1].serialize()), self.instances.items())),
        )

    @classmethod
    def from_design(cls, design):
        m = cls()

        data = design.design_yaml['instances']
        for name in data.keys():
            m.instances[name] = Instance.from_design(design, name)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field('instances', design_yaml, value_types=(dict,))

        for instance_name in design_yaml['instances'].keys():
            Instance.validate_yaml(design_yaml, instance_name, **kw.get('instance', dict()))

        kw['validated'].append(cls.__name__)

        return

    def __init__(self):
        self.instances = dict()

    def get(self, name):
        return self.instances[name]

    def get_instance_by_node(self, name):
        for instance in self.instances.values():
            if name in instance.nodes:
                return instance

        return None


class Instance(ValidateTypeField):
    defaults = dict(
        base_path='/opt/bos',
    )
    name = None
    internal_ip = None
    public_ip = None
    tags = None
    nodes = None
    base_path = None

    def serialize(self, *a, **kw):
        return dict(
            name=self.name,
            internal_ip=self.internal_ip,
            public_ip=self.public_ip,
            tags=self.tags,
            nodes=self.nodes,
        )

    @classmethod
    def from_design(cls, design, name):
        m = cls()

        data = design.design_yaml['instances'][name]

        m.name = name
        m.internal_ip = data['internal_ip']
        m.public_ip = data.get('public_ip', m.internal_ip)
        m.tags = data.get('tags', list())
        m.nodes = data.get('nodes', list())
        m.base_path = data.get('base_path', cls.defaults['base_path'])

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, instance_name):
        cls.validate_field(instance_name, design_yaml['instances'], value_types=(dict,))

        def check_func(k, v, *a, **kw):
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValidationError('invalid ip address of `internal_ip`, "%s" of `instance`, "%s"' % (
                    v, instance_name,
                ))

        cls.validate_field(
            'internal_ip',
            design_yaml['instances'][instance_name],
            value_types=(str,),
            check_func=check_func,
        )

        return

    def __init__(self):
        self.internal_ip = None
        self.public_ip = None
        self.tags = list()
        self.nodes = list()
        self.base_path = self.defaults['base_path']

    def get_validators(self, nodes):
        return list(filter(
            lambda x: nodes[x].is_validator,
            self.nodes,
        ))

    def get_nodes(self, nodes):
        return list(filter(
            lambda x: not nodes[x].is_validator,
            self.nodes,
        ))

    def get_safe_node_name(self, node_name):
        return '%s_%s' % (safe_name(self.name), safe_name(node_name))


class Databases(ValidateTypeField):
    class_engine = None
    backends = None

    def serialize(self, *a, **kw):
        return dict(
            backends=dict(
                map(
                    lambda x: (x[0], x[1].serialize()),
                    self.backends.items(),
                ),
            ),
        )

    @classmethod
    def get_engine_class(cls, engine_name):
        class_name = 'Database%s' % engine_name.replace('-', '_').title()

        return globals()[class_name]

    @classmethod
    def from_design(cls, design):
        m = cls()

        data = design.design_yaml['databases']

        m.backends = dict()
        for name, v in data.items():
            engine_class = cls.get_engine_class(v['engine'])
            m.backends[name] = engine_class.from_design(v)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field('databases', design_yaml, value_types=(dict,))

        for name in design_yaml['databases'].keys():
            cls.validate_field(name, design_yaml['databases'], value_types=(dict,))
            cls.validate_field('engine', design_yaml['databases'][name], value_types=(str,))

        for name, v in design_yaml['databases'].items():
            try:
                engine_class = cls.get_engine_class(v['engine'])
            except KeyError:
                raise ValidationError('unknown database engine, "%s"' % v['engine'])

            engine_class.validate_yaml(design_yaml, name, **kw.get('database', dict()))

        kw['validated'].append(cls.__name__)

        return

    def get(self, name):
        return self.backends[name]


class BaseDatabase:
    def serialize(self, *a, **kw):
        return dict()


class DatabasePostgresql(ValidateTypeField, BaseDatabase):
    default_port = 5432

    host = None
    port = None
    user = None
    password = None
    options = None

    def serialize(self):
        return dict(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            options=self.options,
        )

    @classmethod
    def from_design(cls, data):
        m = cls()

        m.host = data['host']
        m.port = data.get('port', cls.default_port)
        m.user = data['user']
        m.password = data['password']
        m.options = data.get('options', dict())

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, name, **kw):
        db = design_yaml['databases'][name]

        cls.validate_field('host', db, value_types=(str,))
        cls.validate_field('port', db, value_types=(int,), allow_missing=True)
        cls.validate_field('user', db, value_types=(str,))
        cls.validate_field('password', db, value_types=(str,))
        cls.validate_field('options', db, value_types=(str,), allow_missing=True)

        return


class DatabaseMysql(ValidateTypeField, BaseDatabase):
    default_port = 3306

    host = None
    port = None
    user = None
    password = None
    options = None

    def serialize(self):
        return dict(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            options=self.options,
        )

    @classmethod
    def from_design(cls, data):
        m = cls()

        m.host = data['host']
        m.port = data.get('port', cls.default_port)
        m.user = data['user']
        m.password = data['password']
        m.options = data.get('options', dict())

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, name, **kw):
        db = design_yaml['databases'][name]

        cls.validate_field('host', db, value_types=(str,))
        cls.validate_field('port', db, value_types=(int,), allow_missing=True)
        cls.validate_field('user', db, value_types=(str,))
        cls.validate_field('password', db, value_types=(str,))
        cls.validate_field('options', db, value_types=(str,), allow_missing=True)

        return


class DatabaseSqlite(ValidateTypeField, BaseDatabase):
    path = None

    def serialize(self):
        return dict(
            path=self.host,
        )

    @classmethod
    def from_design(cls, data):
        m = cls()

        m.path = data['path']

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, name, **kw):
        db = design_yaml['databases'][name]

        cls.validate_field('path', db, value_types=(str,))

        return


class History(ValidateTypeField):
    trusted = None
    backends = None

    def serialize(self, *a, **kw):
        return dict(
            trusted=self.trusted.serialize(),
            backends=dict(
                map(
                    lambda x: (x[0], x[1].serialize()),
                    self.backends.items(),
                ),
            ),
        )

    @classmethod
    def from_design(cls, design):
        m = cls()

        m.trusted = HistoryTrusted.from_design(design)

        for name, v in design.design_yaml['history']['backends'].items():
            m.backends[name] = HistoryBackend.from_design(design, name)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field('history', design_yaml, value_types=(dict,))

        HistoryTrusted.validate_yaml(design_yaml, **kw.get('trusted', dict()))
        HistoryBackend.validate_yaml(design_yaml, **kw.get('trusted', dict()))

        kw['validated'].append(cls.__name__)

        return

    def __init__(self):
        self.trusted = None
        self.backends = dict()

    def get(self, name):
        return self.backends[name]

    def get_trusted_histories(self, nodes):
        assert isinstance(nodes, Nodes)

        histories = list()

        for node_name in self.trusted.nodes:
            node_data = nodes.get(node_name).serialize()
            history = self.get(node_data['history'])

            histories.append(dict(
                name=node_data['safe_name'],
                getter=history.getter.format(**node_data),
            ))

        return histories


class HistoryTrusted(ValidateTypeField):
    nodes = None

    def serialize(self, *a, **kw):
        return self.nodes

    @classmethod
    def from_design(cls, design):
        m = cls()

        m.nodes = design.design_yaml['history']['trusted']

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        def check_func(k, nodes, *a, **kw):
            if len(nodes) != len(set(nodes)):
                duplicated = list(filter(lambda x: nodes.count(x) > 1, nodes))
                raise ValidationError(
                    'found the duplicated nodes in `trusted`: %s' % (
                        ', '.join(map(lambda x: '"%s"' % x, set(duplicated))),
                    ),
                )

            return

        cls.validate_field(
            'trusted',
            design_yaml['history'],
            value_types=(list, tuple),
            check_func=check_func,
        )

        return

    def __init__(self):
        self.nodes = list()


class HistoryBackend(ValidateTypeField):
    getter = None
    putter = None

    def serialize(self, *a, **kw):
        return dict(
            getter=self.getter,
            putter=self.putter,
        )

    @classmethod
    def from_design(cls, design, name):
        m = cls()

        data = design.design_yaml['history']['backends'][name]

        m.getter = data.get('getter')
        m.putter = data.get('putter')

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field(
            'backends',
            design_yaml['history'],
            value_types=(dict,),
        )

        def check_func_backend(k, v, *a, **kw):
            cls.validate_field('getter', v, value_types=(str,))
            cls.validate_field('putter', v, value_types=(str,))

            return

        for name, v in design_yaml['history']['backends'].items():
            cls.validate_field(
                name,
                design_yaml['history']['backends'],
                value_types=(dict,),
                check_func=check_func_backend,
            )

        return


class Nodes(ValidateTypeField):
    nodes = None

    def serialize(self, *a, **kw):
        return dict(
            nodes=dict(
                map(
                    lambda x: (x[0], x[1].serialize()),
                    self.nodes.items(),
                ),
            ),
        )

    @classmethod
    def from_design(cls, design):
        m = cls()

        for name, v in design.design_yaml['nodes'].items():
            m.nodes[name] = Node.from_design(design, name)

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, **kw):
        cls.validate_field(
            'nodes',
            design_yaml,
            value_types=(dict,),
        )

        secret_seeds = list()
        for name, v in design_yaml['nodes'].items():
            Node.validate_yaml(
                design_yaml,
                name,
                validated=kw.get('validated'),
                **kw.get('node', dict())
            )
            if v is not None and 'secret_seed' in v:
                secret_seed = v.get('secret_seed')
                if secret_seed in secret_seeds:
                    raise ValidationError(
                        'found the duplicated `secret_seed`, "%s" in node, "%s"' % (
                            secret_seed,
                            name,
                        ),
                    )

                secret_seeds.append(secret_seed)

        # check the duplication of secret_seed

        kw['validated'].append(cls.__name__)

        return

    def __init__(self):
        self.nodes = dict()

    def get(self, node_name):
        return self.nodes[node_name]


class Node(ValidateTypeField):
    name = None
    safe_name = None
    hostname = None
    secret_seed = None
    public_address = None
    is_validator = None
    database = None
    history = None
    peer_port = None
    http_port = None

    def serialize(self, *a, **kw):
        return dict(
            name=self.name,
            safe_name=self.safe_name,
            hostname=self.hostname,
            secret_seed=self.secret_seed,
            public_address=self.public_address,
            is_validator=self.is_validator,
            database=self.database,
            history=self.history,
            peer_port=self.peer_port,
            http_port=self.http_port,
        )

    @classmethod
    def get_defaults_design(cls, generate_secret_seed=False):
        return dict(
            secret_seed=Keypair.random().seed().decode(),
        )

    @classmethod
    def from_design(cls, design, name):
        m = cls()

        data = design.design_yaml['nodes'][name]

        m.name = name
        m.safe_name = safe_name(name)
        m.hostname = name
        m.secret_seed = data['secret_seed']
        m.public_address = Keypair.from_seed(m.secret_seed).address().decode()
        m.is_validator = data.get('is_validator', True)  # default is `True`
        m.database = data.get('database', 'default')
        m.history = data.get('history', 'default')
        m.peer_port = data.get('peer_port')
        m.http_port = data.get('http_port')

        return m

    @classmethod
    def validate_yaml(cls, design_yaml, name, **kw):
        allow_missing_fields = kw.get('allow_missing_fields', list())

        if 'Nodes' not in kw.get('validated', list()):
            if 'secret_seed' not in allow_missing_fields:
                def check_func_secret_seed(k, v, *a, **kw):
                    try:
                        Keypair.from_seed(v).address().decode()
                    except DecodeError as e:
                        raise ValidationError('bad `secret_seed`, "%s": %s' % (v, e))

                    return

                cls.validate_field(
                    'secret_seed',
                    design_yaml['nodes'][name],
                    value_types=(str,),
                    check_func=check_func_secret_seed,
                )

            cls.validate_field(
                'is_validator',
                design_yaml['nodes'][name],
                value_types=(bool,),
                allow_missing=True,
            )

            def check_func_common(k, nodes, *a, **kw):
                if len(nodes) != len(set(nodes)):
                    duplicated = list(filter(lambda x: nodes.count(x) > 1, nodes))
                    raise ValidationError(
                        'found the duplicated nodes in `common` of "%s": %s' % (
                            name,
                            ', '.join(map(lambda x: '"%s"' % x, set(duplicated))),
                        ),
                    )
                return

            cls.validate_field(
                'common',
                design_yaml['nodes'][name],
                value_types=(list, tuple),
                allow_missing=True,
                check_func=check_func_common,
            )

        if 'Databases' in kw.get('validated', list()):
            def check_func_database(k, v, *a, **kw):
                if v not in design_yaml['databases']:
                    raise ValidationError(
                        'unknown database, "%s" in `node`, "%s"' % (
                            v, name,
                        ),
                    )

            cls.validate_field(
                'database',
                design_yaml['nodes'][name],
                value_types=(str,),
                allow_missing=True,
                check_func=check_func_database,
            )

        if 'History' in kw.get('validated', list()):
            def check_func_history(k, v, *a, **kw):
                if v not in design_yaml['history']['backends']:
                    raise ValidationError(
                        'unknown history backends, "%s" in `node`, "%s"' % (
                            v, name,
                        ),
                    )

            cls.validate_field(
                'history',
                design_yaml['nodes'][name],
                value_types=(str,),
                allow_missing=True,
                check_func=check_func_history,
            )

            cls.validate_field(
                'peer_port',
                design_yaml['nodes'][name],
                value_types=(int,),
                allow_missing=True,
            )

            cls.validate_field(
                'http_port',
                design_yaml['nodes'][name],
                value_types=(int,),
                allow_missing=True,
            )

        return
