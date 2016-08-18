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
from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common.constants import UpdateMethod
from vitrage.common.constants import VertexProperties
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.host.transformer import HostTransformer
from vitrage.datasources.nova.zone import NOVA_ZONE_DATASOURCE
from vitrage.datasources.nova.zone.transformer import ZoneTransformer
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import TransformerBase
from vitrage.tests import base
from vitrage.tests.mocks import mock_driver as mock_sync

LOG = logging.getLogger(__name__)


# noinspection PyProtectedMember
class NovaHostTransformerTest(base.BaseTest):

    OPTS = [
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PUSH),
    ]

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.transformers = {}
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.OPTS, group=NOVA_HOST_DATASOURCE)
        cls.transformers[NOVA_ZONE_DATASOURCE] = ZoneTransformer(
            cls.transformers, cls.conf)
        cls.transformers[NOVA_HOST_DATASOURCE] = HostTransformer(
            cls.transformers, cls.conf)

    def test_create_placeholder_vertex(self):
        LOG.debug('Nova host transformer test: Test create placeholder vertex')

        # Test setup
        host_name = 'host123'
        timestamp = datetime.datetime.utcnow()
        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        # Test action
        properties = {
            VertexProperties.ID: host_name,
            VertexProperties.TYPE: NOVA_HOST_DATASOURCE,
            VertexProperties.SAMPLE_TIMESTAMP: timestamp
        }
        placeholder = host_transformer.create_placeholder_vertex(**properties)

        # Test assertions
        observed_id_values = placeholder.vertex_id.split(
            TransformerBase.KEY_SEPARATOR)
        expected_id_values = host_transformer._key_values(
            NOVA_HOST_DATASOURCE,
            host_name)
        self.assertEqual(tuple(observed_id_values), expected_id_values)

        observed_time = placeholder.get(VertexProperties.SAMPLE_TIMESTAMP)
        self.assertEqual(observed_time, timestamp)

        observed_subtype = placeholder.get(VertexProperties.TYPE)
        self.assertEqual(observed_subtype, NOVA_HOST_DATASOURCE)

        observed_entity_id = placeholder.get(VertexProperties.ID)
        self.assertEqual(observed_entity_id, host_name)

        observed_category = placeholder.get(VertexProperties.CATEGORY)
        self.assertEqual(observed_category, EntityCategory.RESOURCE)

        is_placeholder = placeholder.get(VertexProperties.IS_PLACEHOLDER)
        self.assertEqual(is_placeholder, True)

    def test_key_values(self):

        LOG.debug('Test key values')

        # Test setup
        host_name = 'host123456'
        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        # Test action
        observed_key_fields = host_transformer._key_values(
            NOVA_HOST_DATASOURCE,
            host_name)

        # Test assertions
        self.assertEqual(EntityCategory.RESOURCE, observed_key_fields[0])
        self.assertEqual(NOVA_HOST_DATASOURCE, observed_key_fields[1])
        self.assertEqual(host_name, observed_key_fields[2])

    def test_snapshot_transform(self):
        LOG.debug('Nova host transformer test: transform entity event')

        # Test setup
        spec_list = mock_sync.simple_host_generators(zone_num=2,
                                                     host_num=4,
                                                     snapshot_events=5)

        host_events = mock_sync.generate_random_events_list(spec_list)

        for event in host_events:
            # Test action
            wrapper = self.transformers[NOVA_HOST_DATASOURCE].transform(event)

            # Test assertions
            self._validate_vertex_props(wrapper.vertex, event)

            neighbors = wrapper.neighbors
            self.assertEqual(1, len(neighbors))
            self._validate_zone_neighbor(neighbors[0], event)

            if SyncMode.SNAPSHOT == event[DSProps.SYNC_MODE]:
                self.assertEqual(EventAction.UPDATE_ENTITY, wrapper.action)
            else:
                self.assertEqual(EventAction.CREATE_ENTITY, wrapper.action)

    def _validate_zone_neighbor(self, zone, event):

        zone_name = tbase.extract_field_value(event, 'zone')
        time = event[DSProps.SAMPLE_DATE]

        zt = self.transformers[NOVA_ZONE_DATASOURCE]
        properties = {
            VertexProperties.ID: zone_name,
            VertexProperties.TYPE: NOVA_ZONE_DATASOURCE,
            VertexProperties.SAMPLE_TIMESTAMP: time
        }
        expected_neighbor = zt.create_placeholder_vertex(**properties)
        self.assertEqual(expected_neighbor, zone.vertex)

        # Validate neighbor edge
        edge = zone.edge
        self.assertEqual(edge.source_id, zone.vertex.vertex_id)
        self.assertEqual(
            edge.target_id,
            self.transformers[NOVA_HOST_DATASOURCE]._create_entity_key(event)
        )
        self.assertEqual(edge.label, EdgeLabel.CONTAINS)

    def _validate_vertex_props(self, vertex, event):

        extract_value = tbase.extract_field_value

        expected_id = extract_value(event, '_info', 'host_name')
        observed_id = vertex[VertexProperties.ID]
        self.assertEqual(expected_id, observed_id)
        self.assertEqual(
            EntityCategory.RESOURCE,
            vertex[VertexProperties.CATEGORY]
        )

        self.assertEqual(
            NOVA_HOST_DATASOURCE,
            vertex[VertexProperties.TYPE]
        )

        expected_timestamp = event[DSProps.SAMPLE_DATE]
        observed_timestamp = vertex[VertexProperties.SAMPLE_TIMESTAMP]
        self.assertEqual(expected_timestamp, observed_timestamp)

        expected_name = extract_value(event, '_info', 'host_name')
        observed_name = vertex[VertexProperties.NAME]
        self.assertEqual(expected_name, observed_name)

        is_placeholder = vertex[VertexProperties.IS_PLACEHOLDER]
        self.assertFalse(is_placeholder)

        is_deleted = vertex[VertexProperties.IS_DELETED]
        self.assertFalse(is_deleted)

    def test_extract_action_type(self):
        LOG.debug('Test extract action type')

        # Test setup
        spec_list = mock_sync.simple_host_generators(
            zone_num=1,
            host_num=1,
            snapshot_events=1,
            snap_vals={DSProps.SYNC_MODE: SyncMode.SNAPSHOT})

        hosts_events = mock_sync.generate_random_events_list(spec_list)
        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        # Test action
        action = host_transformer._extract_action_type(hosts_events[0])

        # Test assertion
        self.assertEqual(EventAction.UPDATE_ENTITY, action)

        # Test setup
        spec_list = mock_sync.simple_host_generators(
            zone_num=1,
            host_num=1,
            snapshot_events=1,
            snap_vals={DSProps.SYNC_MODE: SyncMode.INIT_SNAPSHOT})
        hosts_events = mock_sync.generate_random_events_list(spec_list)
        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        # Test action
        action = host_transformer._extract_action_type(hosts_events[0])

        # Test assertions
        self.assertEqual(EventAction.CREATE_ENTITY, action)

        # TODO(lhartal): To add extract action from update event
