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
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import extract_field_value
import vitrage.graph.utils as graph_utils


LOG = logging.getLogger(__name__)


class ZoneTransformer(ResourceTransformerBase):

    STATE_AVAILABLE = 'available'
    STATE_UNAVAILABLE = 'unavailable'

    def __init__(self, transformers, conf):
        super(ZoneTransformer, self).__init__(transformers, conf)

    def _create_snapshot_entity_vertex(self, entity_event):

        zone_name = extract_field_value(entity_event, 'zoneName')
        is_available = extract_field_value(entity_event,
                                           'zoneState',
                                           'available')
        state = self.STATE_AVAILABLE if is_available \
            else self.STATE_UNAVAILABLE

        return self._create_vertex(entity_event, state, zone_name)

    def _create_update_entity_vertex(self, entity_event):
        LOG.warning('Zone Update is not supported yet')

    def _create_vertex(self, entity_event, state, zone_name):

        metadata = {
            VProps.NAME: zone_name
        }
        entity_key = self._create_entity_key(entity_event)

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]
        update_timestamp = self._format_update_timestamp(None,
                                                         sample_timestamp)

        return graph_utils.create_vertex(
            entity_key,
            entity_id=zone_name,
            entity_category=EntityCategory.RESOURCE,
            entity_type=NOVA_ZONE_DATASOURCE,
            entity_state=state,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_nova_zone_neighbors(entity_event)

    def _create_update_neighbors(self, entity_event):
        return self._create_nova_zone_neighbors(entity_event)

    def _create_nova_zone_neighbors(self, entity_event):
        zone_vertex_id = self._create_entity_key(entity_event)
        neighbors = [self._create_cluster_neighbor(zone_vertex_id)]
        hosts = extract_field_value(entity_event, 'hosts')
        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        if host_transformer:
            for hostname, host_data in hosts.items():

                host_available = extract_field_value(host_data,
                                                     'nova-compute',
                                                     'available')
                host_active = extract_field_value(host_data,
                                                  'nova-compute',
                                                  'active')

                host_state = self.STATE_AVAILABLE \
                    if host_available and host_active \
                    else self.STATE_UNAVAILABLE

                host_neighbor = self._create_host_neighbor(
                    zone_vertex_id,
                    hostname,
                    host_state,
                    entity_event[DSProps.SAMPLE_DATE])

                neighbors.append(host_neighbor)
        else:
            LOG.warning('Cannot find host transformer')

        return neighbors

    @staticmethod
    def _create_cluster_neighbor(zone_vertex_id):

        cluster_vertex = tbase.create_cluster_placeholder_vertex()

        relation_edge = graph_utils.create_edge(
            source_id=cluster_vertex.vertex_id,
            target_id=zone_vertex_id,
            relationship_type=EdgeLabel.CONTAINS)
        return tbase.Neighbor(cluster_vertex, relation_edge)

    def _create_host_neighbor(self, zone_id, host_name,
                              host_state, sample_timestamp):

        host_transformer = self.transformers[NOVA_HOST_DATASOURCE]

        properties = {
            VProps.ID: host_name,
            VProps.SAMPLE_TIMESTAMP: sample_timestamp,
            VProps.TYPE: NOVA_HOST_DATASOURCE
        }
        host_neighbor = \
            host_transformer.create_placeholder_vertex(**properties)
        host_neighbor[VProps.STATE] = host_state
        host_neighbor[VProps.IS_PLACEHOLDER] = False

        relation_edge = graph_utils.create_edge(
            source_id=zone_id,
            target_id=host_neighbor.vertex_id,
            relationship_type=EdgeLabel.CONTAINS)

        return tbase.Neighbor(host_neighbor, relation_edge)

    def _create_entity_key(self, entity_event):

        zone_name = extract_field_value(entity_event, 'zoneName')

        key_fields = self._key_values(NOVA_ZONE_DATASOURCE, zone_name)
        return tbase.build_key(key_fields)

    def get_type(self):
        return NOVA_ZONE_DATASOURCE
