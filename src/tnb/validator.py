from .design import (
    Design,
    Network,
    Instances,
    Databases,
    History,
    Nodes,
)


class Validator:
    design = None
    modules = None
    network = None
    instances = None
    databases = None
    history = None
    nodes = None

    def __init__(self, design):
        assert isinstance(design, Design)

        self.design = design

    def validate(self, **kw):
        validated = list()

        Nodes.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('nodes', dict()))
        Network.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('network', dict()))
        Instances.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('instances', dict()))
        Databases.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('databases', dict()))
        History.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('history', dict()))
        Nodes.validate_yaml(self.design.design_yaml, validated=validated, **kw.get('nodes', dict()))

        return
