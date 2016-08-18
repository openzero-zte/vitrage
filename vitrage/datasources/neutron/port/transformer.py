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

from vitrage.datasources.resource_transformer_base import \
    ResourceTransformerBase

from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EventAction
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.neutron.network import NEUTRON_NETWORK_DATASOURCE
from vitrage.datasources.neutron.port import NEUTRON_PORT_DATASOURCE
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import extract_field_value
from vitrage.datasources.transformer_base import Neighbor

import vitrage.graph.utils as graph_utils

LOG = logging.getLogger(__name__)


class PortTransformer(ResourceTransformerBase):

    UPDATE_ID_PROPERTY = {
        'port.create.end': ('port', 'id'),
        'port.update.end': ('port', 'id'),
        'port.delete.end': ('port_id',),
        None: ('id',)
    }

    FIXED_IPS_PROPERTY = {
        'port.create.end': ('port', 'fixed_ips'),
        'port.update.end': ('port', 'fixed_ips'),
        None: ('fixed_ips',)
    }

    # Event types which need to refer them differently
    UPDATE_EVENT_TYPES = {
        'port.delete.end': EventAction.DELETE_ENTITY,
    }

    def __init__(self, transformers, conf):
        super(PortTransformer, self).__init__(transformers, conf)

    def _create_snapshot_entity_vertex(self, entity_event):

        name = entity_event['name'] if entity_event['name'] else None
        entity_id = entity_event['id']
        state = entity_event['status']
        update_timestamp = entity_event['updated_at']
        project_id = entity_event.get('tenant_id', None)

        return self._create_vertex(entity_event,
                                   name,
                                   entity_id,
                                   state,
                                   update_timestamp,
                                   project_id)

    def _create_update_entity_vertex(self, entity_event):

        event_type = entity_event[DSProps.EVENT_TYPE]
        name = extract_field_value(entity_event, 'port', 'name')
        state = extract_field_value(entity_event, 'port', 'status')
        update_timestamp = \
            extract_field_value(entity_event, 'port', 'updated_at')
        entity_id = extract_field_value(entity_event,
                                        *self.UPDATE_ID_PROPERTY[event_type])
        project_id = extract_field_value(entity_event, 'port', 'tenant_id')

        return self._create_vertex(entity_event,
                                   name,
                                   entity_id,
                                   state,
                                   update_timestamp,
                                   project_id)

    def _create_vertex(self,
                       entity_event,
                       name,
                       entity_id,
                       state,
                       update_timestamp,
                       project_id):
        event_type = entity_event.get(DSProps.EVENT_TYPE, None)
        ip_addresses = []
        if not event_type:
            fixed_ips = extract_field_value(
                entity_event, *self.FIXED_IPS_PROPERTY[event_type])
            ip_addresses = [ip['ip_address'] for ip in fixed_ips]
        metadata = {
            VProps.NAME: name,
            VProps.PROJECT_ID: project_id,
            'ip_addresses': tuple(ip_addresses),
        }

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        return graph_utils.create_vertex(
            self._create_entity_key(entity_event),
            entity_id=entity_id,
            entity_category=EntityCategory.RESOURCE,
            entity_type=NEUTRON_PORT_DATASOURCE,
            entity_state=state,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_port_neighbors(entity_event,
                                           ('device_owner',),
                                           ('device_id',),
                                           ('network_id',))

    def _create_update_neighbors(self, entity_event):
        return self._create_port_neighbors(entity_event,
                                           ('port', 'device_owner'),
                                           ('port', 'device_id'),
                                           ('port', 'network_id'))

    def _create_port_neighbors(self,
                               entity_event,
                               device_owner_property,
                               device_id_property,
                               network_id_property):
        neighbors = [self._create_network_neighbor(entity_event,
                                                   network_id_property)]

        device_owner = \
            extract_field_value(entity_event, *device_owner_property)
        if device_owner == 'compute:nova' or device_owner == 'compute:None':
            instance = self._create_instance_neighbor(
                entity_event,
                device_id_property)
            neighbors.append(instance)

        return neighbors

    def _create_instance_neighbor(self,
                                  entity_event,
                                  instance_id_property):
        port_vitrage_id = self._create_entity_key(entity_event)

        instance_id = extract_field_value(entity_event, *instance_id_property)

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        properties = {
            VProps.ID: instance_id,
            VProps.TYPE: NOVA_INSTANCE_DATASOURCE,
            VProps.SAMPLE_TIMESTAMP: sample_timestamp
        }
        instance_vertex = self.create_placeholder_vertex(**properties)

        relationship_edge = graph_utils.create_edge(
            source_id=port_vitrage_id,
            target_id=instance_vertex.vertex_id,
            relationship_type=EdgeLabel.ATTACHED)

        return Neighbor(instance_vertex, relationship_edge)

    def _create_network_neighbor(self, entity_event, net_id_property):
        port_vitrage_id = self._create_entity_key(entity_event)

        net_id = extract_field_value(entity_event, *net_id_property)

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        properties = {
            VProps.ID: net_id,
            VProps.TYPE: NEUTRON_NETWORK_DATASOURCE,
            VProps.SAMPLE_TIMESTAMP: sample_timestamp
        }

        net_vertex = self.create_placeholder_vertex(**properties)

        relationship_edge = graph_utils.create_edge(
            source_id=net_vertex.vertex_id,
            target_id=port_vitrage_id,
            relationship_type=EdgeLabel.CONTAINS)

        return Neighbor(net_vertex, relationship_edge)

    def _create_entity_key(self, entity_event):
        event_type = entity_event.get(DSProps.EVENT_TYPE, None)
        port_id = extract_field_value(entity_event,
                                      *self.UPDATE_ID_PROPERTY[event_type])

        key_fields = self._key_values(NEUTRON_PORT_DATASOURCE, port_id)

        return tbase.build_key(key_fields)

    def get_type(self):
        return NEUTRON_PORT_DATASOURCE
