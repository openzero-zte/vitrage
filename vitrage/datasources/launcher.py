# Copyright 2016 - Alcatel-Lucent
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

import itertools

from oslo_service import service as os_service
from oslo_utils import importutils as utils
from vitrage.common.constants import UpdateMethod
from vitrage.common.utils import opt_exists
from vitrage.datasources.listener_service import ListenerService

from vitrage.datasources.services import ChangesService
from vitrage.datasources.services import SnapshotsService

CHANGES_INTERVAL = 'changes_interval'


def create_send_to_queue_callback(queue):
    def send_to_queue_callback(event):
        queue.put(event)

    return send_to_queue_callback


class Launcher(object):
    def __init__(self, conf, callback):
        self.conf = conf
        self.callback = callback
        self.snapshot_datasources = self._register_snapshot_datasources(conf)
        self.services = self._register_services()

    def launch(self):
        launcher = os_service.ProcessLauncher(self.conf)
        for service in self.services:
            launcher.launch_service(service, 1)

    @staticmethod
    def _register_snapshot_datasources(conf):
        return {datasource: utils.import_object(conf[datasource].driver, conf)
                for datasource in conf.datasources.types}

    def _register_services(self):
        pull_datasources = self._get_pull_datasources(self.conf)
        changes_services = \
            (ChangesService(self.conf,
                            [self.snapshot_datasources[datasource]],
                            self.conf[datasource].changes_interval,
                            self.callback)
             for datasource in pull_datasources)

        snapshot_service = (SnapshotsService(self.conf,
                                             self.snapshot_datasources,
                                             self.callback),)

        listener_service = (ListenerService(self.conf,
                                            self.snapshot_datasources,
                                            self.callback),)

        return itertools.chain(changes_services,
                               snapshot_service,
                               listener_service)

    @staticmethod
    def _get_pull_datasources(conf):
        return (datasource for datasource in conf.datasources.types
                if conf[datasource].update_method.lower() == UpdateMethod.PULL
                and opt_exists(conf[datasource], CHANGES_INTERVAL))
