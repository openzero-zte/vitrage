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
from oslo_utils import importutils as utils

from vitrage.common.constants import UpdateMethod
from vitrage.datasources.launcher import Launcher
from vitrage.datasources.listener_service import ListenerService
from vitrage.datasources.nagios import NAGIOS_DATASOURCE
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources.zabbix import ZABBIX_DATASOURCE
from vitrage.tests import base


CHANGES_INTERVAL = 'changes_interval'
LOG = logging.getLogger(__name__)
ZABBIX_DATASOURCE_NONE = '_'.join((ZABBIX_DATASOURCE, UpdateMethod.NONE))
ZABBIX_DATASOURCE_PULL = '_'.join((ZABBIX_DATASOURCE, UpdateMethod.PULL))
ZABBIX_DATASOURCE_PUSH = ZABBIX_DATASOURCE
ZABBIX_DATASOURCE_PULL_NO_INTERVAL = \
    '_'.join((ZABBIX_DATASOURCE, UpdateMethod.PULL, 'no_interval'))


class DatasourceUpdateMethod(base.BaseTest):

    DATASOURCES_OPTS = [
        cfg.ListOpt('types',
                    default=[NOVA_HOST_DATASOURCE,
                             NOVA_INSTANCE_DATASOURCE,
                             NAGIOS_DATASOURCE,
                             ZABBIX_DATASOURCE_NONE,
                             ZABBIX_DATASOURCE_PULL,
                             ZABBIX_DATASOURCE_PUSH,
                             ZABBIX_DATASOURCE_PULL_NO_INTERVAL],
                    help='Names of supported data sources'),
        cfg.StrOpt('notification_topic',
                   default='vitrage_notifications',
                   help='Vitrage configured notifications topic')
    ]

    NOVA_HOST_OPTS = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.nova.host.driver.HostDriver',
                   help='Nova host driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.NONE,
                   help='None: updates only via Vitrage periodic snapshots.'
                        'Pull: updates every [changes_interval] seconds.'
                        'Push: updates by getting notifications from the'
                        ' datasource itself.',
                   required=True),
    ]

    NOVA_INSTANCE_OPTS = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.nova.instance.driver.'
                           'InstanceDriver',
                   help='Nova instance driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PUSH,
                   required=True),
    ]

    NAGIOS_OPTS = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.nagios.driver.NagiosDriver',
                   help='Nagios driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PULL,
                   required=True),
        cfg.IntOpt('changes_interval',
                   default=30,
                   min=30,
                   help='interval between checking changes in nagios'
                        ' data source'),
    ]

    ZABBIX_OPTS_PUSH = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.zabbix.driver.ZabbixDriver',
                   help='Zabbix driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PUSH,
                   required=True),
        cfg.IntOpt('changes_interval',
                   default=30,
                   min=30,
                   help='interval between checking changes in zabbix'
                        ' data source'),
    ]

    ZABBIX_OPTS_PULL = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.zabbix.driver.ZabbixDriver',
                   help='Zabbix driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PULL,
                   required=True),
        cfg.IntOpt('changes_interval',
                   default=30,
                   min=30,
                   help='interval between checking changes in zabbix'
                        ' data source'),
    ]

    ZABBIX_OPTS_PULL_NO_INTERVAL = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.zabbix.driver.ZabbixDriver',
                   help='Zabbix driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.PULL,
                   required=True),
    ]

    ZABBIX_OPTS_NONE = [
        cfg.StrOpt('driver',
                   default='vitrage.datasources.zabbix.driver.ZabbixDriver',
                   help='Zabbix driver class path',
                   required=True),
        cfg.StrOpt('update_method',
                   default=UpdateMethod.NONE,
                   required=True),
        cfg.IntOpt('changes_interval',
                   default=30,
                   min=30,
                   help='interval between checking changes in zabbix'
                        ' data source'),
    ]

    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.DATASOURCES_OPTS, group='datasources')
        cls.conf.register_opts(cls.NOVA_HOST_OPTS, group=NOVA_HOST_DATASOURCE)
        cls.conf.register_opts(cls.NOVA_INSTANCE_OPTS,
                               group=NOVA_INSTANCE_DATASOURCE)
        cls.conf.register_opts(cls.NAGIOS_OPTS, group=NAGIOS_DATASOURCE)
        cls.conf.register_opts(cls.ZABBIX_OPTS_NONE,
                               group=ZABBIX_DATASOURCE_NONE)
        cls.conf.register_opts(cls.ZABBIX_OPTS_PULL,
                               group=ZABBIX_DATASOURCE_PULL)
        cls.conf.register_opts(cls.ZABBIX_OPTS_PUSH,
                               group=ZABBIX_DATASOURCE_PUSH)
        cls.conf.register_opts(cls.ZABBIX_OPTS_PULL_NO_INTERVAL,
                               group=ZABBIX_DATASOURCE_PULL_NO_INTERVAL)

    def test_datasource_update_method_none(self):
        none_drivers = tuple(driver for driver in self.conf.datasources.types
                             if self.conf[driver].update_method
                             == UpdateMethod.NONE)
        self.assertSequenceEqual(none_drivers,
                                 (NOVA_HOST_DATASOURCE,
                                  ZABBIX_DATASOURCE_NONE))

    def test_datasource_update_method_push(self):
        drivers = {driver: utils.import_class(self.conf[driver].driver)
                   for driver in self.conf.datasources.types}
        push_drivers = ListenerService._get_push_drivers(
            drivers=drivers, conf=self.conf)
        self.assertSequenceEqual(set(push_drivers), {utils.import_class(
            self.conf[NOVA_INSTANCE_DATASOURCE].driver), utils.import_class(
            self.conf[ZABBIX_DATASOURCE_PUSH].driver)})

    def test_datasource_update_method_pull(self):
        pull_drivers = tuple(Launcher._get_pull_datasources(self.conf))
        self.assertSequenceEqual(pull_drivers,
                                 (NAGIOS_DATASOURCE,
                                  ZABBIX_DATASOURCE_PULL))

    def test_datasource_update_method_pull_with_no_changes_interval(self):
        pull_drivers = tuple(Launcher._get_pull_datasources(self.conf))
        self.assertNotIn(ZABBIX_DATASOURCE_PULL_NO_INTERVAL, pull_drivers)

    def test_datasources_notification_topic(self):
        self.assertEqual(self.conf.datasources.notification_topic,
                         'vitrage_notifications')
