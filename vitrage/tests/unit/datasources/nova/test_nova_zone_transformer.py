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

import datetime

from oslo_config import cfg
from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import UpdateMethod
from vitrage.common.constants import VertexProperties
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.host.transformer import HostTransformer
from vitrage.datasources.nova.zone import NOVA_ZONE_DATASOURCE
from vitrage.datasources.nova.zone.transformer import ZoneTransformer
from vitrage.datasources import OPENSTACK_CLUSTER
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import TransformerBase
from vitrage.tests import base
from vitrage.tests.mocks import mock_driver as mock_sync

LOG = logging.getLogger(__name__)


# noinspection PyProtectedMember
class NovaZoneTransformerTest(base.BaseTest):

    OPTS = [
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PUSH),
    ]

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.transformers = {}
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.OPTS, group=NOVA_ZONE_DATASOURCE)
        cls.transformers[NOVA_HOST_DATASOURCE] = \
            HostTransformer(cls.transformers, cls.conf)
        cls.transformers[NOVA_ZONE_DATASOURCE] = \
            ZoneTransformer(cls.transformers, cls.conf)

    def test_create_placeholder_vertex(self):

        LOG.debug('Zone transformer test: create placeholder vertex')

        # Test setup
        zone_name = 'zone123'
        timestamp = datetime.datetime.utcnow()
        zone_transformer = self.transformers[NOVA_ZONE_DATASOURCE]

        # Test action
        properties = {
            VertexProperties.ID: zone_name,
            VertexProperties.TYPE: NOVA_ZONE_DATASOURCE,
            VertexProperties.SAMPLE_TIMESTAMP: timestamp
        }
        placeholder = zone_transformer.create_placeholder_vertex(**properties)

        # Test assertions
        observed_id_values = placeholder.vertex_id.split(
            TransformerBase.KEY_SEPARATOR)
        expected_id_values = self.transformers[NOVA_ZONE_DATASOURCE].\
            _key_values(NOVA_ZONE_DATASOURCE, zone_name)
        self.assertEqual(tuple(observed_id_values), expected_id_values)

        observed_time = placeholder.get(VertexProperties.SAMPLE_TIMESTAMP)
        self.assertEqual(observed_time, timestamp)

        observed_subtype = placeholder.get(VertexProperties.TYPE)
        self.assertEqual(observed_subtype, NOVA_ZONE_DATASOURCE)

        observed_entity_id = placeholder.get(VertexProperties.ID)
        self.assertEqual(observed_entity_id, zone_name)

        observed_category = placeholder.get(VertexProperties.CATEGORY)
        self.assertEqual(observed_category, EntityCategory.RESOURCE)

        is_placeholder = placeholder.get(VertexProperties.IS_PLACEHOLDER)
        self.assertEqual(is_placeholder, True)

    def test_key_values(self):
        LOG.debug('Zone transformer test: get key values')

        # Test setup
        zone_name = 'zone123'
        zone_transformer = self.transformers[NOVA_ZONE_DATASOURCE]

        # Test action
        observed_key_fields = zone_transformer._key_values(
            NOVA_ZONE_DATASOURCE,
            zone_name)

        # Test assertions
        self.assertEqual(EntityCategory.RESOURCE, observed_key_fields[0])
        self.assertEqual(
            NOVA_ZONE_DATASOURCE,
            observed_key_fields[1]
        )
        self.assertEqual(zone_name, observed_key_fields[2])

    def test_extract_key(self):
        pass

    def test_snapshot_transform(self):
        LOG.debug('Nova zone transformer test: transform entity event')

        # Test setup
        spec_list = mock_sync.simple_zone_generators(zone_num=1,
                                                     host_num=1,
                                                     snapshot_events=5)
        zone_events = mock_sync.generate_random_events_list(spec_list)

        for event in zone_events:
            # Test action
            wrapper = self.transformers[NOVA_ZONE_DATASOURCE].transform(event)

            # Test assertions
            vertex = wrapper.vertex
            self._validate_vertex_props(vertex, event)

            neighbors = wrapper.neighbors
            self.assertEqual(2, len(neighbors))
            self._validate_neighbors(neighbors, vertex.vertex_id, event)

    def _validate_neighbors(self, neighbors, zone_vertex_id, event):

        cluster_neighbors_counter = 0

        for neighbor in neighbors:
            vertex_type = neighbor.vertex.get(VertexProperties.TYPE)

            if OPENSTACK_CLUSTER == vertex_type:
                cluster_neighbors_counter += 1
                self._validate_cluster_neighbor(neighbor, zone_vertex_id)
            else:
                hosts = tbase.extract_field_value(event, 'hosts')
                self._validate_host_neighbor(neighbor,
                                             zone_vertex_id,
                                             hosts,
                                             event[DSProps.SYNC_MODE])

        self.assertEqual(1,
                         cluster_neighbors_counter,
                         'Zone can belongs to only one Cluster')

    def _validate_host_neighbor(self,
                                host_neighbor,
                                zone_vertex_id,
                                hosts,
                                sync_mode):

        host_vertex = host_neighbor.vertex
        host_vertex_id = host_vertex.get(VertexProperties.ID)

        host_dic = hosts[host_vertex_id]
        self.assertIsNotNone(hosts[host_vertex_id])

        host_available = tbase.extract_field_value(
            host_dic,
            'nova-compute', 'available'
        )
        host_active = tbase.extract_field_value(
            host_dic,
            'nova-compute', 'active'
        )

        if host_available and host_active:
            expected_host_state = ZoneTransformer.STATE_AVAILABLE
        else:
            expected_host_state = ZoneTransformer.STATE_UNAVAILABLE
        self.assertEqual(
            expected_host_state,
            host_vertex.get(VertexProperties.STATE)
        )

        is_placeholder = host_vertex[VertexProperties.IS_PLACEHOLDER]
        self.assertFalse(is_placeholder)

        is_deleted = host_vertex[VertexProperties.IS_DELETED]
        self.assertFalse(is_deleted)

        # Validate neighbor edge
        edge = host_neighbor.edge
        self.assertEqual(edge.target_id, host_neighbor.vertex.vertex_id)
        self.assertEqual(edge.source_id, zone_vertex_id)
        self.assertEqual(edge.label, EdgeLabel.CONTAINS)

    def _validate_cluster_neighbor(self, cluster_neighbor, zone_vertex_id):

        expected_cluster_neighbor = tbase.create_cluster_placeholder_vertex()
        self.assertEqual(expected_cluster_neighbor, cluster_neighbor.vertex)

        # Validate neighbor edge
        edge = cluster_neighbor.edge
        self.assertEqual(edge.source_id, cluster_neighbor.vertex.vertex_id)
        self.assertEqual(edge.target_id, zone_vertex_id)
        self.assertEqual(edge.label, EdgeLabel.CONTAINS)

    def _validate_vertex_props(self, vertex, event):

        zone_transform = self.transformers[NOVA_ZONE_DATASOURCE]

        extract_value = tbase.extract_field_value

        expected_id = extract_value(event, 'zoneName')
        observed_id = vertex[VertexProperties.ID]
        self.assertEqual(expected_id, observed_id)

        self.assertEqual(EntityCategory.RESOURCE,
                         vertex[VertexProperties.CATEGORY])

        self.assertEqual(NOVA_ZONE_DATASOURCE,
                         vertex[VertexProperties.TYPE])

        expected_timestamp = event[DSProps.SAMPLE_DATE]
        observed_timestamp = vertex[VertexProperties.SAMPLE_TIMESTAMP]
        self.assertEqual(expected_timestamp, observed_timestamp)

        expected_name = extract_value(event, 'zoneName')
        observed_name = vertex[VertexProperties.NAME]
        self.assertEqual(expected_name, observed_name)

        is_zone_available = extract_value(event, 'zoneState', 'available')

        if is_zone_available:
            expected_state = zone_transform.STATE_AVAILABLE
        else:
            expected_state = zone_transform.STATE_UNAVAILABLE

        observed_state = vertex[VertexProperties.STATE]
        self.assertEqual(expected_state, observed_state)

        is_placeholder = vertex[VertexProperties.IS_PLACEHOLDER]
        self.assertFalse(is_placeholder)

        is_deleted = vertex[VertexProperties.IS_DELETED]
        self.assertFalse(is_deleted)
