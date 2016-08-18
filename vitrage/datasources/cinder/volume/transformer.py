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
from vitrage.common.constants import EventAction
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.cinder.volume import CINDER_VOLUME_DATASOURCE
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources.resource_transformer_base import \
    ResourceTransformerBase
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import build_key
from vitrage.datasources.transformer_base import extract_field_value
from vitrage.datasources.transformer_base import Neighbor
import vitrage.graph.utils as graph_utils


LOG = logging.getLogger(__name__)


class CinderVolumeTransformer(ResourceTransformerBase):

    # Event types which need to refer them differently
    UPDATE_EVENT_TYPES = {
        'volume.delete.end': EventAction.DELETE_ENTITY,
        'volume.detach.start': EventAction.DELETE_RELATIONSHIP,
        'volume.attach.end': EventAction.UPDATE_RELATIONSHIP
    }

    def __init__(self, transformers, conf):
        super(CinderVolumeTransformer, self).__init__(transformers, conf)

    def _create_snapshot_entity_vertex(self, entity_event):

        volume_name = extract_field_value(entity_event, 'display_name')
        volume_id = extract_field_value(entity_event, 'id')
        volume_state = extract_field_value(entity_event, 'status')
        project_id = entity_event.get('os-vol-tenant-attr:tenant_id', None)
        timestamp = extract_field_value(entity_event, 'created_at')

        return self._create_vertex(entity_event,
                                   volume_name,
                                   volume_id,
                                   volume_state,
                                   project_id,
                                   timestamp)

    def _create_update_entity_vertex(self, entity_event):

        volume_name = extract_field_value(entity_event, 'display_name')
        volume_id = extract_field_value(entity_event, 'volume_id')
        volume_state = extract_field_value(entity_event, 'status')
        project_id = entity_event.get('tenant_id', None)
        timestamp = entity_event.get('updated_at', None)

        return self._create_vertex(entity_event,
                                   volume_name,
                                   volume_id,
                                   volume_state,
                                   project_id,
                                   timestamp)

    def _create_vertex(self,
                       entity_event,
                       volume_name,
                       volume_id,
                       volume_state,
                       project_id,
                       update_timestamp):
        metadata = {
            VProps.NAME: volume_name,
            VProps.PROJECT_ID: project_id,
        }

        entity_key = self._create_entity_key(entity_event)

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        return graph_utils.create_vertex(
            entity_key,
            entity_id=volume_id,
            entity_category=EntityCategory.RESOURCE,
            entity_type=CINDER_VOLUME_DATASOURCE,
            entity_state=volume_state,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_instance_neighbors(entity_event,
                                               'attachments',
                                               'server_id')

    def _create_update_neighbors(self, entity_event):
        return self._create_instance_neighbors(entity_event,
                                               'volume_attachment',
                                               'instance_uuid')

    def _create_entity_key(self, entity_event):

        is_update_event = tbase.is_update_event(entity_event)
        id_field_path = 'volume_id' if is_update_event else 'id'
        volume_id = extract_field_value(entity_event, id_field_path)

        key_fields = self._key_values(CINDER_VOLUME_DATASOURCE, volume_id)
        return build_key(key_fields)

    def _create_instance_neighbors(self,
                                   entity_event,
                                   attachments_property,
                                   instance_id_property):
        transformer = self.transformers[NOVA_INSTANCE_DATASOURCE]

        if transformer:
            return [self._create_instance_neighbor(entity_event,
                                                   attachment,
                                                   transformer,
                                                   instance_id_property)
                    for attachment in entity_event[attachments_property]]
        else:
            LOG.warning('Cannot find instance transformer')

    def _create_instance_neighbor(self,
                                  entity_event,
                                  attachment,
                                  instance_transformer,
                                  instance_id_property):
        volume_vitrage_id = self._create_entity_key(entity_event)

        instance_id = attachment[instance_id_property]

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        properties = {
            VProps.ID: instance_id,
            VProps.TYPE: NOVA_INSTANCE_DATASOURCE,
            VProps.SAMPLE_TIMESTAMP: sample_timestamp
        }
        instance_vertex = \
            instance_transformer.create_placeholder_vertex(
                **properties)

        relationship_edge = graph_utils.create_edge(
            source_id=volume_vitrage_id,
            target_id=instance_vertex.vertex_id,
            relationship_type=EdgeLabel.ATTACHED)

        return Neighbor(instance_vertex, relationship_edge)

    def get_type(self):
        return CINDER_VOLUME_DATASOURCE
