import itertools
import logging
from pprint import pprint  # noqa
from graphviz import Digraph
from .design import (
    Design,
    Network,
    Regions,
    Instances,
    Databases,
    History,
    Nodes,
)
from .util import (
    calculate_tags_distance,
    get_distances_by_region,
)
from .quorum import (
    RegionalQuorum,
    print_quorum,
)


log = logging.getLogger(__name__)


def flatten_items(l):
    return list(itertools.chain(*l.values()))


class Builder:
    design = None
    modules = None
    network = None
    instances = None
    regions = None
    databases = None
    history = None
    nodes = None
    number_of_connected_regions = None

    color_gradient = ('gray70', 'gray66', 'gray61', 'gray57', 'gray52', 'gray48', 'gray43')
    distance_distributtion = None

    def __init__(self, design):
        assert isinstance(design, Design)
        self.design = design

        self.network = Network.from_design(self.design)
        self.regions = Regions.from_design(self.design)
        self.instances = Instances.from_design(self.design)
        self.databases = Databases.from_design(self.design)
        self.history = History.from_design(self.design)
        self.nodes = Nodes.from_design(self.design)

        self.number_of_connected_regions = self.network.number_of_connected_regions
        if self.number_of_connected_regions > len(self.regions.regions) - 1:
            self.number_of_connected_regions = len(self.regions.regions) - 1

    def make_quorums(self):
        '''
        Scenario
        ========

        * set the failure, `Fn`
        * number of regions is `Rn`
        * number of validators in region is `Vn`
        * number of common in 2 regions is `Cn`
        * number of extra in region is `En`

        1. combine the validators by regions
            1. basically one region will have one quorum
            1. each validator in region can be 'common' and 'extra'
        1. calculte the number of 'common' in each region: Cn <= Vn - Fn
        1. traverse region to check the 'safety'
            1. make region pairs by distance
                1. each region makes quorum intersection with 2 other regions
            1. region pairs: Fn(safety) <= 2Cn - Vn - 1
            1. to satisfy the safety, choose the common validators
        1. traverse region to check the 'liveness'
            1. region pairs: Fn(liveness) <= Vn - Cn
            1. to satisfy the liveness, choose the common validators
        '''

        # validators
        instances_by_node = dict()
        regions_by_node = dict()
        nodes_by_region = dict()
        for instance_name, instance in self.instances.instances.items():
            region = self.regions.get_region_by_instance(instance_name)
            nodes_by_region.setdefault(region.name, dict(validators=list(), nodes=list()))
            nodes_by_region[region.name]['validators'].extend(instance.get_validators(self.nodes.nodes))
            nodes_by_region[region.name]['nodes'].extend(instance.get_nodes(self.nodes.nodes))

            for n in instance.nodes:
                instances_by_node[n] = instance_name
                regions_by_node[n] = region.name

        validators_by_region = dict()
        for region_name, v in nodes_by_region.items():
            validators_by_region[region_name] = v['validators']

        # distance
        distance_tags = dict(map(
            lambda x: (x[0], x[1].tags),
            self.regions.regions.items(),
        ))

        distances_by_tags = dict()
        sorted_regions = sorted(distance_tags.keys())
        for index, region_name in enumerate(sorted_regions):
            for other in sorted_regions[index + 1:]:
                ratio = calculate_tags_distance(
                    distance_tags[region_name],
                    distance_tags[other],
                )

                key = tuple(sorted((region_name, other)))
                distances_by_tags[key] = ratio

        distances = dict()
        for region in sorted_regions:
            distances[region] = get_distances_by_region(distances_by_tags, region)

        regions = RegionalQuorum(
            validators_by_region,
            self.network.number_of_failure,
            2,
        ).compose(distances)

        for r, v in regions.items():
            log.debug('\n' + print_quorum(r, v, regions, validators_by_region[r], self.network.number_of_failure))

        all_nodes = sorted(itertools.chain(
            *map(
                lambda x: x.nodes,
                self.instances.instances.values(),
            )
        ))

        quorums = dict()
        for v in all_nodes:
            region_name = regions_by_node[v]
            validators = regions[region_name]

            quorums[v] = dict(
                node=v,
                validators=dict(
                    extra=list(set(validators_by_region[region_name]) & set(validators)),
                ),
                region=region_name,
                instance=instances_by_node[v],
            )

            for rn, vs in regions.items():
                if rn == region_name:
                    continue

                quorums[v]['validators'][rn] = list(set(validators) & set(vs))

        return quorums

    def make_quorums_graph(self, quorums, dpi=None, output_format=None, output=None):
        if dpi is None:
            dpi = 300

        if output_format is None:
            output_format = 'svg'

        g = Digraph('G', format=output_format, engine='fdp')

        g.graph_attr.update(fontname='monospace', size='100,100', dpi=str(dpi), fontsize='10', style='rounded', splines='curved')
        g.edge_attr.update(fontname='monospace', fontsize='6', penwidth='0.5', arrowsize='0.5', arrowhead=None, color='gray')
        g.node_attr.update(
            fontname='monospace',
            fontsize='10',
            style='filled',
            color='snow',
            fontcolor='snow',
            fillcolor='crimson',
            shape='circle',
            penwidth='0'
        )

        connected = dict()
        quorum_names = list(quorums.keys())
        for v0 in quorum_names:
            region_name = quorums[v0]['region']
            g.node(region_name)

            for v1 in quorum_names:
                other = quorums[v1]['region']
                if region_name == other:
                    continue

                key = tuple(sorted((region_name, other)))
                if region_name not in quorums[v1]['validators']:
                    continue

                connected.setdefault(key, list())
                connected[key] = set(connected[key]) | set(quorums[v1]['validators'][region_name])

        range_count = (max(map(lambda x: len(x), connected.values())), min(map(lambda x: len(x), connected.values())))
        for key, vs in connected.items():
            count = len(vs)
            penwidth = (count - range_count[1]) / range_count[0] * 10
            g.edge(
                *key,
                arrowhead='dot',
                arrowtail='dot',
                dir='both',
                penwidth=str(penwidth if penwidth > 0.5 else 0.5),
                label=str(count))

        if output is not None:
            g.render(output, cleanup=True)

            return

        return g.pipe(format=output_format)

    def make_quorum_validators_graph(self, quorums, output_format=None, dpi=None, output=None):
        assert type(quorums) in (dict,)

        if output_format is None:
            output_format = 'svg'

        if dpi is None:
            dpi = 150

        g = Digraph('G', format=output_format, engine='fdp')

        g.graph_attr.update(fontname='monospace', size='100,100', dpi=str(dpi), fontsize='10', style='rounded', splines='curved')
        g.edge_attr.update(fontname='monospace', fontsize='6', penwidth='0.5', arrowsize='0.5', arrowhead=None, color='gray')
        g.node_attr.update(
            fontname='monospace',
            fontsize='10',
            style='filled',
            color='snow',
            fontcolor='snow',
            fillcolor='crimson',
            shape='circle',
            penwidth='0'
        )

        for instance_name, instance in self.instances.instances.items():
            with g.subgraph(name='cluster_%s' % instance_name) as c:
                c.attr(style='filled, dashed, rounded', color='gray68', fillcolor='gray96', fontcolor='gray22')
                c.attr(label=instance_name)

                for v in instance.nodes:
                    c.node('%s%s' % (instance_name, v), label=v)

        range_connected = None
        quorum_names = list(quorums.keys())
        for index, v0 in enumerate(quorum_names):
            for v1 in quorum_names[index + 1:]:
                vs0 = flatten_items(quorums[v0]['validators'])
                vs1 = flatten_items(quorums[v1]['validators'])

                connected = len(set(vs0) & set(vs1))

                if range_connected is None:
                    range_connected = [connected, connected]
                    continue

                if connected > range_connected[0]:
                    range_connected[0] = connected
                elif connected < range_connected[1]:
                    range_connected[1] = connected

        connected_quorums = list()
        for index, v0 in enumerate(quorum_names[:]):
            for v1 in quorum_names[index + 1:]:
                vs0 = flatten_items(quorums[v0]['validators'])
                vs1 = flatten_items(quorums[v1]['validators'])
                if v0 not in vs1:
                    continue

                key = tuple(sorted((v0, v1)))
                if key in connected_quorums:
                    continue

                connected_quorums.append(key)

                connected_nodes = set(vs0) & set(vs1)
                len_connected = len(connected_nodes)
                if range_connected[0] - range_connected[1] < 1:
                    weight = 0
                else:
                    weight = ((len_connected - range_connected[1]) / (range_connected[0] - range_connected[1]))
                penwidth = ((weight * 10) ** 1.9) / 10
                # color = self.color_gradient[round(weight * len(self.color_gradient)) - 1]
                g.edge(
                    '%s%s' % (quorums[v0]['instance'], v0),
                    '%s%s' % (quorums[v1]['instance'], v1),
                    arrowsize='0.4',
                    arrowhead='dot',
                    arrowtail='dot',
                    dir='both',
                    penwidth=str(penwidth if penwidth > 1 else 1.5),
                    label=str(len(connected_nodes)),
                    fontcolor='#aaaaaaff',
                    color='#aaaaaa44',
                )

        if output is not None:
            g.render(output, cleanup=True)

            return

        return g.pipe(format=output_format)

    def make_quorum_validators_direct_graph(self, quorums, output_format=None, dpi=None, output=None):
        assert type(quorums) in (dict,)

        if output_format is None:
            output_format = 'svg'

        if dpi is None:
            dpi = 150

        g = Digraph('G', format=output_format, engine='fdp')

        g.graph_attr.update(fontname='monospace', size='100,100', dpi=str(dpi), fontsize='10', style='rounded', splines='curved')
        g.edge_attr.update(fontname='monospace', fontsize='6', penwidth='0.5', arrowsize='0.5', arrowhead=None, color='gray')
        g.node_attr.update(
            fontname='monospace',
            fontsize='10',
            style='filled',
            color='snow',
            fontcolor='snow',
            fillcolor='crimson',
            shape='circle',
            penwidth='0'
        )

        for instance_name, instance in self.instances.instances.items():
            with g.subgraph(name='cluster_%s' % instance_name) as c:
                c.attr(style='filled, dashed, rounded', color='gray68', fillcolor='gray96', fontcolor='gray22')
                c.attr(label=instance_name)

                for v in instance.nodes:
                    c.node('%s%s' % (instance_name, v), label=v)

        connected_quorums = list()
        quorum_names = list(quorums.keys())
        for index, v0 in enumerate(quorum_names[:]):
            for v1 in quorum_names[index + 1:]:
                vs1 = flatten_items(quorums[v1]['validators'])
                if v0 not in vs1:
                    continue

                key = tuple(sorted((v0, v1)))
                if key in connected_quorums:
                    continue

                if v0 not in vs1:
                    continue

                connected_quorums.append(key)

                g.edge(
                    '%s%s' % (quorums[v0]['instance'], v0),
                    '%s%s' % (quorums[v1]['instance'], v1),
                    arrowsize='0.4',
                    arrowhead='dot',
                    arrowtail='dot',
                    dir='both',
                    penwidth=str(0.3),
                    fontcolor='#aaaaaaff',
                    color='#aaaaaaaa',
                )

        if output is not None:
            g.render(output, cleanup=True)

            return

        return g.pipe(format=output_format)
