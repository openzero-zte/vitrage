# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Defines interface for Graph access and manipulation

Functions in this module are imported into the vitrage.graph namespace.
Call these functions from vitrage.graph namespace and not the
vitrage.graph.driver namespace.

"""
import abc
import six

from vitrage.graph.driver.elements import Edge
from vitrage.graph.driver.elements import Vertex
from vitrage.graph.driver.notifier import Notifier


class Direction(object):
    OUT = 1
    IN = 2
    BOTH = 3


@six.add_metaclass(abc.ABCMeta)
class Graph(object):
    def __init__(self, name, graph_type):
        """Create a Graph instance

        :type name: str
        :type graph_type: str
        :rtype: Graph
        """
        self.name = name
        self.graph_type = graph_type
        self.root_id = None
        self.notifier = Notifier()

    def subscribe(self, function):
        self.notifier.subscribe(function)

    def is_subscribed(self):
        return self.notifier.is_subscribed()

    def get_item(self, item):
        if isinstance(item, Edge):
            return self.get_edge(item.source_id, item.target_id, item.label)
        if isinstance(item, Vertex):
            return self.get_vertex(item.vertex_id)

    @abc.abstractmethod
    def copy(self):
        """Create a copy of the graph

        :return: A copy of the graph
        :rtype: Graph
        """
        pass

    @abc.abstractmethod
    def num_vertices(self):
        """Number of vertices in the graph

        :return:
        :rtype: int
        """
        pass

    @abc.abstractmethod
    def num_edges(self):
        """Number of edges in the graph

        :return:
        :rtype: int
        """
        pass

    @abc.abstractmethod
    def add_vertex(self, v):
        """Add a vertex to the graph

        A copy of Vertex v will be added to the graph.

        Example:
        --------
        graph = Graph()
        v = Vertex(vertex_id=1, properties={prop_key:prop_value})
        graph.add_vertex(v)

        :param v: the vertex to add
        :type v: Vertex
        """
        pass

    @abc.abstractmethod
    def add_edge(self, e):
        """Add an edge to the graph

        A copy of Edge e will be added to the graph.

        Example:
        --------
        graph = Graph()

        v1_prop = {'prop_key':'some value for my first vertex'}
        v2_prop = {'prop_key':'another value for my second vertex'}
        v1 = Vertex(vertex_id=1, properties=v1_prop)
        v2 = Vertex(vertex_id=2, properties=v2_prop)
        graph.add_vertex(v1)
        graph.add_vertex(v2)

        e_prop = {'edge_prop':'and here is my edge property value'}
        e = Edge(source_id=v1.vertex_id, target_id=v2.vertex_id,
                 label='BELONGS', properties=e_prop)
        graph.add_edge(e)

        :param e: the edge to add
        :type e: Edge
        """
        pass

    @abc.abstractmethod
    def get_vertex(self, v_id):
        """Fetch a vertex from the graph

        :param v_id: vertex id
        :type v_id: str

        :return: the vertex or None if it does not exist
        :rtype: Vertex
        """
        pass

    @abc.abstractmethod
    def get_edge(self, source_id, target_id, label):
        """Fetch an edge from the graph,

        Fetch an edge from the graph, according to its two vertices and label

        :param source_id: vertex id of the source vertex
        :type source_id: str or None

        :param target_id: vertex id of the target vertex
        :type target_id: str

        :param label: the label property of the edge
        :type label: str or None

        :return: The edge between the two vertices or None
        :rtype: Edge
        """
        pass

    @abc.abstractmethod
    def get_edges(self, v_id, direction=Direction.BOTH,
                  attr_filter=None):
        """Fetch multiple edges from the graph,

        Fetch an edge from the graph, according to its two vertices and label

        EXAMPLE
        -------
        v2_edges1 = g.get_edges(
            v_id=v2.vertex_id,
            attr_filter={'LABEL': 'ON'})

        v2_edges2 = g.get_edges(
            v_id=v2.vertex_id,
            attr_filter={'LABEL': ['ON', 'WITH']})

        :param v_id: vertex id a vertex
        :type v_id: str

        :param direction: specify In/Out/Both for edge direction
        :type direction: int

        :param attr_filter: expected keys and values
        :type attr_filter: dict

        :return: All edges matching the requirements
        :rtype: list of Edge
        """
        pass

    @abc.abstractmethod
    def update_vertex(self, v, hard_update=False):
        """Update the vertex properties

        Update an existing vertex and create it if non existing.
        Hard update: can be used to remove existing fields.

        :param v: the vertex with the new data
        :type v: Vertex
        :param hard_update: if True, original properties will be removed.
        :type hard_update: bool
        """
        pass

    @abc.abstractmethod
    def update_edge(self, e, hard_update=False):
        """Update the edge properties

        Update an existing edge and create it if non existing.
        Hard update: can be used to remove existing fields.

        :param e: the edge with the new data
        :type e: Edge
        :param hard_update: if True, original properties will be removed.
        :type hard_update: bool
        """
        pass

    @abc.abstractmethod
    def remove_vertex(self, v):
        """Remove Vertex v and its edges from the graph

        :type v: Vertex
        """
        pass

    @abc.abstractmethod
    def remove_edge(self, e):
        """Remove an edge from the graph

        :type e: Edge
        """
        pass

    @abc.abstractmethod
    def get_vertices(self, vertex_attr_filter=None, query_dict=None):
        """Get vertices list with an optional match filter

        To filter the vertices, specify property values for
        the vertices

        Example:
        --------
        graph = Graph()

        v1_prop = {'prop_key':'some value for my first vertex'}
        v2_prop = {'prop_key':'another value for my second vertex'}
        v3_prop = {'prop_key':'YES'}
        v1 = Vertex(vertex_id=1, properties=v1_prop)
        v2 = Vertex(vertex_id=2, properties=v2_prop)
        v3 = Vertex(vertex_id=3, properties=v3_prop)
        graph.add_vertex(v1)
        graph.add_vertex(v2)
        graph.add_vertex(v3)

        all_vertices = graph.get_vertices()
        for v in all_vertices:
            do something with v
        filtered_vertices_list = graph.get_vertices(
                                    vertex_attr_filter={'prop_key':['YES']})

        :param vertex_attr_filter: expected keys and values
        :type vertex_attr_filter dict
        :param query_dict: expected query
        :type query_dict dict
        :return: A list of vertices that match the requested query
        :rtype: list of Vertex
        """
        pass

    @abc.abstractmethod
    def neighbors(self, v_id, vertex_attr_filter=None,
                  edge_attr_filter=None, direction=Direction.BOTH):
        """Get vertices that are neighboring to v_id vertex

        To filter the neighboring vertices, specify property values for
        the vertices or for the edges connecting them.

        Example:
        --------
        graph = Graph()

        v1_prop = {'prop_key':'some value for my first vertex'}
        v2_prop = {'prop_key':'another value for my second vertex'}
        v3_prop = {'prop_key':'YES'}
        v1 = Vertex(vertex_id=1, properties=v1_prop)
        v2 = Vertex(vertex_id=2, properties=v2_prop)
        v3 = Vertex(vertex_id=3, properties=v3_prop)
        graph.add_vertex(v1)
        graph.add_vertex(v2)
        graph.add_vertex(v3)

        e_prop = {'edge_prop':'and here is my edge property value'}
        e1 = Edge(source_id=v1.vertex_id, target_id=v2.vertex_id,
                 label='BELONGS', properties=e_prop)
        e2 = Edge(source_id=v1.vertex_id, target_id=v3.vertex_id,
                 label='ON', properties=e_prop)
        graph.add_edge(e1)
        graph.add_edge(e2)

        vertices_list1 = graph.neighbors(v_id=v1.vertex_id,
                               vertex_attr_filter={'prop_key':'YES'},
                               edge_attr_filter={'LABEL':'ON})
        vertices_list2 = graph.neighbors(v_id=v1.vertex_id,
                               vertex_attr_filter={'prop_key':['YES', 'CAT']},
                               edge_attr_filter={'LABEL':['ON', 'WITH']})

        :param direction:
        :param v_id: vertex id
        :type v_id: str
        :param vertex_attr_filter: expected keys and values
        :type vertex_attr_filter dict
        :param edge_attr_filter: expected keys and values
        :type edge_attr_filter: dict
        :return: A list of vertices that match the requested query
        :rtype: list of Vertex
        """
        pass

    @abc.abstractmethod
    def json_output_graph(self, **kwargs):
        pass

    @abc.abstractmethod
    def union(self, other_graph):
        pass
