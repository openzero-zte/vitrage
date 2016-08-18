# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,  software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND,  either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import SyncMode
from vitrage.datasources.neutron.base import NeutronBase
from vitrage.datasources.neutron.port import NEUTRON_PORT_DATASOURCE


# noinspection PyAbstractClass
class PortDriver(NeutronBase):

    @staticmethod
    def get_event_types(conf):
        return ['port.create.end',
                'port.update.end',
                'port.delete.end']

    @staticmethod
    def enrich_event(event, event_type):
        event[DSProps.EVENT_TYPE] = event_type

        return PortDriver.make_pickleable([event], NEUTRON_PORT_DATASOURCE,
                                          SyncMode.UPDATE)[0]

    def get_all(self, sync_mode):
        return self.make_pickleable(
            self.client.list_ports()['ports'],
            NEUTRON_PORT_DATASOURCE,
            sync_mode)
