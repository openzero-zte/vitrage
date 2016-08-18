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

from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common.datetime_utils import change_time_str_format
from vitrage.common.datetime_utils import format_unix_timestamp
from vitrage.datasources.alarm_properties import AlarmProperties as AlarmProps
from vitrage.datasources.alarm_transformer_base import AlarmTransformerBase
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.static_physical import SWITCH
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import Neighbor
from vitrage.datasources.zabbix.properties import ZabbixProperties as ZProps
from vitrage.datasources.zabbix.properties import ZabbixTriggerSeverity \
    as TriggerSeverity
from vitrage.datasources.zabbix.properties import ZabbixTriggerValue\
    as TriggerValue
from vitrage.datasources.zabbix import ZABBIX_DATASOURCE


import vitrage.graph.utils as graph_utils

LOG = logging.getLogger(__name__)


class ZabbixTransformer(AlarmTransformerBase):

    def __init__(self, transformers, conf):
        super(ZabbixTransformer, self).__init__(transformers, conf)

    def _create_snapshot_entity_vertex(self, entity_event):
        return self._create_vertex(entity_event)

    def _create_update_entity_vertex(self, entity_event):
        return self._create_vertex(entity_event)

    def _create_vertex(self, entity_event):
        self._unify_time_format(entity_event)

        update_timestamp = entity_event[ZProps.TIMESTAMP]

        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]

        update_timestamp = self._format_update_timestamp(update_timestamp,
                                                         sample_timestamp)

        zabbix_hostname = entity_event[ZProps.ZABBIX_RESOURCE_NAME]
        vitrage_hostname = entity_event[ZProps.RESOURCE_NAME]
        entity_event[ZProps.DESCRIPTION] = entity_event[ZProps.DESCRIPTION]\
            .replace(zabbix_hostname, vitrage_hostname)

        value = entity_event[ZProps.VALUE]
        entity_state = AlarmProps.INACTIVE_STATE if \
            value == TriggerValue.OK else AlarmProps.ACTIVE_STATE

        metadata = {
            VProps.NAME: entity_event[ZProps.DESCRIPTION],
            VProps.SEVERITY: TriggerSeverity.str(
                entity_event[ZProps.PRIORITY]),
            VProps.RAWTEXT: entity_event[ZProps.RAWTEXT]
        }

        return graph_utils.create_vertex(
            self._create_entity_key(entity_event),
            entity_category=EntityCategory.ALARM,
            entity_type=entity_event[DSProps.SYNC_TYPE],
            entity_state=entity_state,
            sample_timestamp=sample_timestamp,
            update_timestamp=update_timestamp,
            metadata=metadata)

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_zabbix_neighbors(entity_event)

    def _create_update_neighbors(self, entity_event):
        return self._create_zabbix_neighbors(entity_event)

    def _create_zabbix_neighbors(self, entity_event):
        self._unify_time_format(entity_event)

        vitrage_id = self._create_entity_key(entity_event)
        timestamp = entity_event[ZProps.TIMESTAMP]

        resource_type = entity_event[ZProps.RESOURCE_TYPE]
        if resource_type == NOVA_HOST_DATASOURCE or resource_type == SWITCH:
            return [self._create_neighbor(
                vitrage_id,
                timestamp,
                resource_type,
                entity_event[ZProps.RESOURCE_NAME])]

        return []

    def _create_neighbor(self,
                         vitrage_id,
                         sample_timestamp,
                         resource_type,
                         resource_name):
        transformer = self.transformers[resource_type]

        if transformer:
            properties = {
                VProps.TYPE: resource_type,
                VProps.ID: resource_name,
                VProps.SAMPLE_TIMESTAMP: sample_timestamp
            }
            resource_vertex = transformer.create_placeholder_vertex(
                **properties)

            relationship_edge = graph_utils.create_edge(
                source_id=vitrage_id,
                target_id=resource_vertex.vertex_id,
                relationship_type=EdgeLabel.ON)

            return Neighbor(resource_vertex, relationship_edge)

        LOG.warning('Cannot transform host, host transformer does not exist')
        return None

    def _ok_status(self, entity_event):
        return entity_event[ZProps.VALUE] == TriggerValue.OK

    def _create_entity_key(self, entity_event):

        sync_type = entity_event[DSProps.SYNC_TYPE]
        alarm_id = entity_event[ZProps.TRIGGER_ID]
        resource_name = entity_event[ZProps.RESOURCE_NAME]
        return tbase.build_key(self._key_values(sync_type,
                                                resource_name,
                                                alarm_id))

    @staticmethod
    def _unify_time_format(entity_event):
        try:
            entity_event[ZProps.TIMESTAMP] = format_unix_timestamp(
                entity_event[ZProps.LAST_CHANGE], tbase.TIMESTAMP_FORMAT)
        except ValueError:
            entity_event[ZProps.TIMESTAMP] = change_time_str_format(
                entity_event[ZProps.LAST_CHANGE],
                ZProps.ZABBIX_TIMESTAMP_FORMAT,
                tbase.TIMESTAMP_FORMAT)

    def get_type(self):
        return ZABBIX_DATASOURCE
