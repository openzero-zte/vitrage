# Copyright 2016 Nokia
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging

from vitrage_tempest_tests.tests.api.topology.base import BaseTopologyTest
import vitrage_tempest_tests.tests.utils as utils
from vitrageclient.exc import ClientException

LOG = logging.getLogger(__name__)
NOVA_QUERY = '{"and": [{"==": {"category": "RESOURCE"}},' \
             '{"==": {"is_deleted": false}},' \
             '{"==": {"is_placeholder": false}},' \
             '{"or": [{"==": {"type": "openstack.cluster"}},' \
             '{"==": {"type": "nova.instance"}},' \
             '{"==": {"type": "nova.host"}},' \
             '{"==": {"type": "nova.zone"}}]}]}'


class TestTopology(BaseTopologyTest):
    """Topology test class for Vitrage API tests."""

    NUM_INSTANCE = 3
    NUM_VOLUME = 1

    @classmethod
    def setUpClass(cls):
        super(TestTopology, cls).setUpClass()

    def test_compare_api_and_cli(self):
        """compare_api_and_cli

        This test validate correctness of topology graph:
         cli via api
        """
        api_graph = self.vitrage_client.topology.get()
        cli_graph = utils.run_vitrage_command('vitrage topology show',
                                              self.conf)
        self._compare_graphs(api_graph, cli_graph)

    def test_default_graph(self):
        """default_graph

        This test validate correctness of default topology graph
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE,
                                  num_volumes=self.NUM_VOLUME)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get()
            graph = self._create_graph_from_graph_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1,
                host_edges=self.NUM_INSTANCE + 1,
                instance_entities=self.NUM_INSTANCE,
                instance_edges=2 * self.NUM_INSTANCE + self.NUM_VOLUME,
                volume_entities=self.NUM_VOLUME,
                volume_edges=self.NUM_VOLUME)
            num_entities = self.num_default_entities + self.NUM_VOLUME + \
                2 * self.NUM_INSTANCE + self.num_default_networks + \
                self.num_default_ports
            num_edges = self.num_default_edges + 3 * self.NUM_INSTANCE + \
                self.NUM_VOLUME + self.num_default_ports

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             num_entities,
                                             num_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_graph_with_query(self):
        """graph_with_query

        This test validate correctness of topology graph
        with query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE,
                                  num_volumes=self.NUM_VOLUME)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                query=self._graph_query())
            graph = self._create_graph_from_graph_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1,
                host_edges=self.NUM_INSTANCE + 1,
                instance_entities=self.NUM_INSTANCE,
                instance_edges=self.NUM_INSTANCE)
            num_entities = self.num_default_entities + self.NUM_INSTANCE
            num_edges = self.num_default_edges + self.NUM_INSTANCE

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             num_entities,
                                             num_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_nova_tree(self):
        """nova_tree

        This test validate correctness of topology tree
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE,
                                  num_volumes=self.NUM_VOLUME)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                graph_type='tree', query=NOVA_QUERY)
            graph = self._create_graph_from_tree_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1,
                host_edges=self.NUM_INSTANCE + 1,
                instance_entities=self.NUM_INSTANCE,
                instance_edges=self.NUM_INSTANCE)
            num_entities = self.num_default_entities + self.NUM_INSTANCE
            num_edges = self.num_default_edges + self.NUM_INSTANCE

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             num_entities,
                                             num_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_tree_with_query(self):
        """tree_with_query

        This test validate correctness of topology tree
        with query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                graph_type='tree', query=self._tree_query())
            graph = self._create_graph_from_tree_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1, host_edges=1)

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             self.num_default_entities,
                                             self.num_default_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_tree_with_depth_exclude_instance(self):
        """tree_with_query

        This test validate correctness of topology tree
        with query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                limit=2, graph_type='tree', query=NOVA_QUERY)
            graph = self._create_graph_from_tree_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1, host_edges=1)

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             self.num_default_entities,
                                             self.num_default_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_tree_with_depth_include_instance(self):
        """tree_with_query

        This test validate correctness of topology tree
        with query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                limit=3, graph_type='tree', query=NOVA_QUERY)
            graph = self._create_graph_from_tree_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1,
                host_edges=self.NUM_INSTANCE + 1,
                instance_entities=self.NUM_INSTANCE,
                instance_edges=self.NUM_INSTANCE)
            num_entities = self.num_default_entities + self.NUM_INSTANCE
            num_edges = self.num_default_edges + self.NUM_INSTANCE

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             num_entities,
                                             num_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_graph_with_root_and_depth_exclude_instance(self):
        """tree_with_query

        This test validate correctness of topology graph
        with root and depth exclude instance
       """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                limit=2, root='RESOURCE:openstack.cluster')
            graph = self._create_graph_from_graph_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1, host_edges=1)

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             self.num_default_entities,
                                             self.num_default_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_graph_with_root_and_depth_include_instance(self):
        """graph_with_root_and_depth_include_instance

        This test validate correctness of topology graph
        with root and depth include instance
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                limit=3, root='RESOURCE:openstack.cluster')
            graph = self._create_graph_from_graph_dictionary(api_graph)
            entities = self._entities_validation_data(
                host_entities=1,
                host_edges=self.NUM_INSTANCE + 1,
                instance_entities=self.NUM_INSTANCE,
                instance_edges=self.NUM_INSTANCE)
            num_entities = self.num_default_entities + self.NUM_INSTANCE
            num_edges = self.num_default_edges + self.NUM_INSTANCE

            # Test Assertions
            self._validate_graph_correctness(graph,
                                             num_entities,
                                             num_edges,
                                             entities)
        finally:
            self._rollback_to_default()

    def test_graph_with_depth_and_no_root(self):
        """graph_with_depth_and_no_root

        This test validate correctness of topology
        graph with depth and without root
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE,
                                  num_volumes=self.NUM_VOLUME)

            # Calculate expected results
            self.vitrage_client.topology.get(limit=2,
                                             root='RESOURCE:openstack.cluster')
        except ClientException as e:
            self.assertEqual(403, e.code)
            self.assertEqual(
                e.message,
                "Graph-type 'graph' requires a 'root' with 'depth'")
        finally:
            self._rollback_to_default()

    def test_graph_with_no_match_query(self):
        """graph_with_no_match_query

        This test validate correctness of topology graph
        with no match query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE,
                                  num_volumes=self.NUM_VOLUME)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                query=self._graph_no_match_query())

            # Test Assertions
            self.assertEqual(
                0,
                len(api_graph['nodes']), 'num of vertex node')
            self.assertEqual(
                0,
                len(api_graph['links']), 'num of edges')
        finally:
            self._rollback_to_default()

    def test_tree_with_no_match_query(self):
        """tree_with_no_match_query

        This test validate correctness of topology tree
        with no match query
        """
        try:
            # Action
            self._create_entities(num_instances=self.NUM_INSTANCE)

            # Calculate expected results
            api_graph = self.vitrage_client.topology.get(
                graph_type='tree', query=self._tree_no_match_query())

            # Test Assertions
            self.assertEqual({}, api_graph)
        finally:
            self._rollback_to_default()
