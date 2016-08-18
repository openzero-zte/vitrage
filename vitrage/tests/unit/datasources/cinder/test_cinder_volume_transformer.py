# Copyright 2016 - Nokia
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
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.cinder.volume import CINDER_VOLUME_DATASOURCE
from vitrage.datasources.cinder.volume.transformer \
    import CinderVolumeTransformer
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources.nova.instance.transformer import InstanceTransformer
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import TransformerBase
from vitrage.tests import base
from vitrage.tests.mocks import mock_driver as mock_sync

LOG = logging.getLogger(__name__)


class TestCinderVolumeTransformer(base.BaseTest):

    OPTS = [
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PUSH),
    ]

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.transformers = {}
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.OPTS, group=CINDER_VOLUME_DATASOURCE)
        cls.transformers[CINDER_VOLUME_DATASOURCE] = \
            CinderVolumeTransformer(cls.transformers, cls.conf)
        cls.transformers[NOVA_INSTANCE_DATASOURCE] = \
            InstanceTransformer(cls.transformers, cls.conf)

    def test_create_placeholder_vertex(self):
        LOG.debug('Cinder Volume transformer test: Create placeholder '
                  'vertex')

        # Tests setup
        volume_id = 'Instance123'
        timestamp = datetime.datetime.utcnow()
        properties = {
            VProps.ID: volume_id,
            VProps.TYPE: CINDER_VOLUME_DATASOURCE,
            VProps.SAMPLE_TIMESTAMP: timestamp
        }
        transformer = self.transformers[CINDER_VOLUME_DATASOURCE]

        # Test action
        placeholder = transformer.create_placeholder_vertex(**properties)

        # Test assertions
        observed_id_values = placeholder.vertex_id.split(
            TransformerBase.KEY_SEPARATOR)
        expected_id_values = transformer._key_values(CINDER_VOLUME_DATASOURCE,
                                                     volume_id)
        self.assertEqual(tuple(observed_id_values), expected_id_values)

        observed_time = placeholder.get(VProps.SAMPLE_TIMESTAMP)
        self.assertEqual(observed_time, timestamp)

        observed_type = placeholder.get(VProps.TYPE)
        self.assertEqual(observed_type, CINDER_VOLUME_DATASOURCE)

        observed_entity_id = placeholder.get(VProps.ID)
        self.assertEqual(observed_entity_id, volume_id)

        observed_category = placeholder.get(VProps.CATEGORY)
        self.assertEqual(observed_category, EntityCategory.RESOURCE)

        is_placeholder = placeholder.get(VProps.IS_PLACEHOLDER)
        self.assertEqual(is_placeholder, True)

    def test_key_values(self):
        LOG.debug('Cinder Volume transformer test: get key values')

        # Test setup
        volume_type = CINDER_VOLUME_DATASOURCE
        volume_id = '12345'
        transformer = self.transformers[CINDER_VOLUME_DATASOURCE]

        # Test action
        observed_key_fields = transformer._key_values(volume_type,
                                                      volume_id)

        # Test assertions
        self.assertEqual(EntityCategory.RESOURCE, observed_key_fields[0])
        self.assertEqual(CINDER_VOLUME_DATASOURCE, observed_key_fields[1])
        self.assertEqual(volume_id, observed_key_fields[2])

    def test_snapshot_transform(self):
        LOG.debug('Cinder Volume transformer test: transform entity event '
                  'snapshot')

        # Test setup
        spec_list = mock_sync.simple_volume_generators(volume_num=3,
                                                       instance_num=7,
                                                       snapshot_events=7)
        static_events = mock_sync.generate_random_events_list(spec_list)

        for event in static_events:
            # Test action
            wrapper = self.transformers[CINDER_VOLUME_DATASOURCE].transform(
                event)

            # Test assertions
            vertex = wrapper.vertex
            self._validate_volume_vertex_props(vertex, event)

            neighbors = wrapper.neighbors
            self.assertEqual(1, len(neighbors))
            self._validate_neighbors(neighbors, vertex.vertex_id, event)

    def test_update_transform(self):
        LOG.debug('Cinder Volume transformer test: transform entity event '
                  'update')

        # Test setup
        spec_list = mock_sync.simple_volume_generators(volume_num=3,
                                                       instance_num=7,
                                                       update_events=7)
        static_events = mock_sync.generate_random_events_list(spec_list)

        for event in static_events:
            # Test action
            wrapper = self.transformers[CINDER_VOLUME_DATASOURCE].transform(
                event)

            # Test assertions
            vertex = wrapper.vertex
            self._validate_volume_vertex_props(vertex, event)

            neighbors = wrapper.neighbors
            self.assertEqual(1, len(neighbors))
            self._validate_neighbors(neighbors, vertex.vertex_id, event)

    def _validate_volume_vertex_props(self, vertex, event):

        is_update_event = tbase.is_update_event(event)

        self.assertEqual(EntityCategory.RESOURCE, vertex[VProps.CATEGORY])
        self.assertEqual(event[DSProps.SYNC_TYPE], vertex[VProps.TYPE])

        id_field_path = 'volume_id' if is_update_event else 'id'
        self.assertEqual(
            tbase.extract_field_value(event, id_field_path),
            vertex[VProps.ID])

        self.assertEqual(event[DSProps.SAMPLE_DATE],
                         vertex[VProps.SAMPLE_TIMESTAMP])

        name_field_path = 'display_name'
        self.assertEqual(
            tbase.extract_field_value(event, name_field_path),
            vertex[VProps.NAME])

        state_field_path = 'status'
        self.assertEqual(
            tbase.extract_field_value(event, state_field_path),
            vertex[VProps.STATE])

        self.assertFalse(vertex[VProps.IS_PLACEHOLDER])
        self.assertFalse(vertex[VProps.IS_DELETED])

    def _validate_neighbors(self, neighbors, volume_vertex_id, event):
        instance_counter = 0

        for neighbor in neighbors:
            is_update_event = tbase.is_update_event(event)
            instance_id = event['volume_attachment'][0]['instance_uuid'] if \
                is_update_event else event['attachments'][0]['server_id']
            self._validate_instance_neighbor(neighbor,
                                             instance_id,
                                             volume_vertex_id)
            instance_counter += 1

        self.assertEqual(1,
                         instance_counter,
                         'Volume can be belonged to only one instance')

    def _validate_instance_neighbor(self,
                                    instance_neighbor,
                                    instance_id,
                                    volume_vertex_id):
        # validate neighbor vertex
        self.assertEqual(EntityCategory.RESOURCE,
                         instance_neighbor.vertex[VProps.CATEGORY])
        self.assertEqual(NOVA_INSTANCE_DATASOURCE,
                         instance_neighbor.vertex[VProps.TYPE])
        self.assertEqual(instance_id, instance_neighbor.vertex[VProps.ID])
        self.assertTrue(instance_neighbor.vertex[VProps.IS_PLACEHOLDER])
        self.assertFalse(instance_neighbor.vertex[VProps.IS_DELETED])

        # Validate neighbor edge
        edge = instance_neighbor.edge
        self.assertEqual(edge.target_id, instance_neighbor.vertex.vertex_id)
        self.assertEqual(edge.source_id, volume_vertex_id)
        self.assertEqual(edge.label, EdgeLabel.ATTACHED)
