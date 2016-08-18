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

from oslo_config import cfg
from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common.constants import UpdateMethod
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common.datetime_utils import format_unix_timestamp
from vitrage.datasources.alarm_properties import AlarmProperties as AlarmProps
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.host.transformer import HostTransformer
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.transformer_base import TransformerBase
from vitrage.datasources.zabbix.properties import ZabbixProperties\
    as ZabbixProps
from vitrage.datasources.zabbix.properties import ZabbixTriggerSeverity
from vitrage.datasources.zabbix.properties import ZabbixTriggerValue
from vitrage.datasources.zabbix.transformer import ZabbixTransformer
from vitrage.datasources.zabbix import ZABBIX_DATASOURCE
from vitrage.tests import base
from vitrage.tests.mocks import mock_driver as mock_sync


LOG = logging.getLogger(__name__)


# noinspection PyProtectedMember
class ZabbixTransformerTest(base.BaseTest):

    OPTS = [
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PULL),
    ]

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.transformers = {}
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.OPTS, group=ZABBIX_DATASOURCE)
        cls.transformers[NOVA_HOST_DATASOURCE] = \
            HostTransformer(cls.transformers, cls.conf)

    def test_extract_key(self):
        LOG.debug('Test get key from nova instance transformer')

        # Test setup
        spec_list = mock_sync.simple_zabbix_alarm_generators(host_num=1,
                                                             events_num=1)
        zabbix_alarms = mock_sync.generate_sequential_events_list(spec_list)
        transformer = ZabbixTransformer(self.transformers, self.conf)
        event = zabbix_alarms[0]
        self.enrich_event(event)

        # Test action
        observed_key = transformer._create_entity_key(event)

        # Test assertions
        observed_key_fields = observed_key.split(
            TransformerBase.KEY_SEPARATOR)

        self.assertEqual(EntityCategory.ALARM, observed_key_fields[0])
        self.assertEqual(event[DSProps.SYNC_TYPE], observed_key_fields[1])
        self.assertEqual(event[ZabbixProps.RESOURCE_NAME],
                         observed_key_fields[2])
        self.assertEqual(event[ZabbixProps.TRIGGER_ID],
                         observed_key_fields[3])

    def test_zabbix_alarm_transform(self):
        LOG.debug('Zabbix alarm transformer test: transform entity event')

        # Test setup
        spec_list = mock_sync.simple_zabbix_alarm_generators(host_num=4,
                                                             events_num=10)
        zabbix_alarms = mock_sync.generate_sequential_events_list(spec_list)

        for alarm in zabbix_alarms:
            # Test action
            self.enrich_event(alarm, format_timestamp=False)
            wrapper = ZabbixTransformer(self.transformers, self.conf)\
                .transform(alarm)
            self._validate_vertex(wrapper.vertex, alarm)

            neighbors = wrapper.neighbors
            self.assertEqual(1, len(neighbors))
            neighbor = neighbors[0]

            # Right now we are support only host as a resource
            if neighbor.vertex[VProps.TYPE] == NOVA_HOST_DATASOURCE:
                self._validate_host_neighbor(neighbors[0], alarm)

            self._validate_action(alarm, wrapper)

    def _validate_action(self, alarm, wrapper):
        sync_mode = alarm[DSProps.SYNC_MODE]
        if sync_mode in (SyncMode.SNAPSHOT, SyncMode.UPDATE):
            if alarm[ZabbixProps.VALUE] == ZabbixTriggerValue.OK:
                self.assertEqual(EventAction.DELETE_ENTITY, wrapper.action)
            else:
                self.assertEqual(EventAction.UPDATE_ENTITY, wrapper.action)
        else:
            self.assertEqual(EventAction.CREATE_ENTITY, wrapper.action)

    def _validate_vertex(self, vertex, event):

        self.assertEqual(EntityCategory.ALARM, vertex[VProps.CATEGORY])
        self.assertEqual(event[DSProps.SYNC_TYPE], vertex[VProps.TYPE])
        self.assertEqual(event[ZabbixProps.DESCRIPTION],
                         vertex[VProps.NAME])

        event_status = event[ZabbixProps.VALUE]

        if event_status == ZabbixTriggerValue.OK:
            self.assertEqual(AlarmProps.INACTIVE_STATE,
                             vertex[VProps.STATE])
        else:
            self.assertEqual(AlarmProps.ACTIVE_STATE,
                             vertex[VProps.STATE])

        event_severity = ZabbixTriggerSeverity.str(
            event[ZabbixProps.PRIORITY])
        self.assertEqual(event_severity, vertex[VProps.SEVERITY])

        self.assertFalse(vertex[VProps.IS_DELETED])
        self.assertFalse(vertex[VProps.IS_PLACEHOLDER])

    def _validate_host_neighbor(self, neighbor, event):

        host_vertex = neighbor.vertex

        key_fields = host_vertex.vertex_id.split(TransformerBase.KEY_SEPARATOR)

        self.assertEqual(EntityCategory.RESOURCE, key_fields[0])
        self.assertEqual(NOVA_HOST_DATASOURCE, key_fields[1])
        self.assertEqual(event[ZabbixProps.RESOURCE_NAME], key_fields[2])

        self.assertFalse(host_vertex[VProps.IS_DELETED])
        self.assertTrue(host_vertex[VProps.IS_PLACEHOLDER])

        self.assertEqual(EntityCategory.RESOURCE, host_vertex[VProps.CATEGORY])
        self.assertEqual(event[ZabbixProps.RESOURCE_NAME],
                         host_vertex[VProps.ID])
        self.assertEqual(NOVA_HOST_DATASOURCE, host_vertex[VProps.TYPE])

        edge = neighbor.edge
        self.assertEqual(EdgeLabel.ON, edge.label)

        alarm_key = ZabbixTransformer(self.transformers, self.conf).\
            _create_entity_key(event)
        self.assertEqual(alarm_key, edge.source_id)
        self.assertEqual(host_vertex.vertex_id, edge.target_id)

    @staticmethod
    def enrich_event(event, format_timestamp=True):
        if format_timestamp:
            event[ZabbixProps.TIMESTAMP] = format_unix_timestamp(
                event[ZabbixProps.LAST_CHANGE], tbase.TIMESTAMP_FORMAT)
