# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,  software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND,  either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging

from vitrage import clients
from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import SyncMode
from vitrage.datasources.cinder.volume import CINDER_VOLUME_DATASOURCE
from vitrage.datasources.driver_base import DriverBase

LOG = logging.getLogger(__name__)


class CinderVolumeDriver(DriverBase):

    def __init__(self, conf):
        super(CinderVolumeDriver, self).__init__()
        self._client = None
        self.conf = conf

    @property
    def client(self):
        if not self._client:
            self._client = clients.cinder_client(self.conf)
        return self._client

    @staticmethod
    def extract_events(volumes):
        return [volume.__dict__ for volume in volumes]

    def get_all(self, sync_mode):
        return self.make_pickleable(
            self.extract_events(self.client.volumes.list(
                search_opts={'all_tenants': 1})),
            CINDER_VOLUME_DATASOURCE,
            sync_mode,
            'manager')

    @staticmethod
    def enrich_event(event, event_type):
        event[DSProps.EVENT_TYPE] = event_type

        return CinderVolumeDriver.make_pickleable([event],
                                                  CINDER_VOLUME_DATASOURCE,
                                                  SyncMode.UPDATE)[0]

    @staticmethod
    def get_event_types(conf):
        return ['volume.create.start',
                'volume.create.end',
                'volume.attach.start',
                'volume.attach.end',
                'volume.detach.start',
                'volume.detach.end',
                'volume.delete.start',
                'volume.delete.end']
