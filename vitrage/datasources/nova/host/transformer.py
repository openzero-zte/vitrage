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

from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.zone import NOVA_ZONE_DATASOURCE
from vitrage.datasources.resource_transformer_base import \
    ResourceTransformerBase
from vitrage.datasources import transformer_base
from vitrage.datasources.transformer_base import extract_field_value
from vitrage.datasources.transformer_base import Neighbor
import vitrage.graph.utils as graph_utils


LOG = logging.getLogger(__name__)


class HostTransformer(ResourceTransformerBase):

    def __init__(self, transformers, conf):
        super(HostTransformer, self).__init__(transformers, conf)

    def _create_snapshot_entity_vertex(self, entity_event):

        host_name = extract_field_value(entity_event, '_info', 'host_name')
        return self._create_vertex(entity_event, host_name)

    def _create_update_entity_vertex(self, entity_event):
        LOG.warning('Host Update is not supported yet')

    def _create_vertex(self, entity_event, host_name):

        metadata = {VProps.NAME: host_name}
        entity_key = self._create_entity_key(entity_event)

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]
        update_timestamp = self._format_update_timestamp(None,
                                                         sample_timestamp)

        return graph_utils.create_vertex(
            entity_key,
            entity_id=host_name,
            entity_category=EntityCategory.RESOURCE,
            entity_type=NOVA_HOST_DATASOURCE,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_nova_host_neighbors(entity_event)

    def _create_update_neighbors(self, entity_event):
        return self._create_nova_host_neighbors(entity_event)

    def _create_nova_host_neighbors(self, entity_event):
        neighbors = []

        # Support snapshot and snapshot_init events only
        zone_neighbor = self._create_zone_neighbor(
            entity_event,
            entity_event[DSProps.SAMPLE_DATE],
            self._create_entity_key(entity_event),
            'zone')

        if zone_neighbor is not None:
            neighbors.append(zone_neighbor)

        return neighbors

    def _create_zone_neighbor(self,
                              entity_event,
                              sample_timestamp,
                              host_vertex_id,
                              zone_name_path):

        zone_transformer = self.transformers[NOVA_ZONE_DATASOURCE]

        if zone_transformer:

            zone_name = extract_field_value(entity_event, zone_name_path)

            properties = {
                VProps.ID: zone_name,
                VProps.TYPE: NOVA_ZONE_DATASOURCE,
                VProps.SAMPLE_TIMESTAMP: sample_timestamp
            }
            zone_neighbor = zone_transformer.create_placeholder_vertex(
                **properties)

            relation_edge = graph_utils.create_edge(
                source_id=zone_neighbor.vertex_id,
                target_id=host_vertex_id,
                relationship_type=EdgeLabel.CONTAINS)
            return Neighbor(zone_neighbor, relation_edge)
        else:
            LOG.warning('Cannot find zone transformer')

        return None

    def _create_entity_key(self, entity_event):

        host_name = extract_field_value(entity_event, '_info', 'host_name')

        key_fields = self._key_values(NOVA_HOST_DATASOURCE, host_name)
        return transformer_base.build_key(key_fields)

    def get_type(self):
        return NOVA_HOST_DATASOURCE
