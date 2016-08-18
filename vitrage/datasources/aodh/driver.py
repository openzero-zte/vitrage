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

from oslo_log import log

from vitrage import clients
from vitrage.datasources.alarm_driver_base import AlarmDriverBase
from vitrage.datasources.aodh import AODH_DATASOURCE
from vitrage.datasources.aodh.properties import AodhProperties as AodhProps
from vitrage.datasources.aodh.properties import AodhState

LOG = log.getLogger(__name__)


class AodhDriver(AlarmDriverBase):
    def __init__(self, conf):
        super(AodhDriver, self).__init__()
        self._client = None
        self.conf = conf

    @property
    def client(self):
        if not self._client:
            self._client = clients.ceilometer_client(self.conf)
        return self._client

    def _sync_type(self):
        return AODH_DATASOURCE

    def _alarm_key(self, alarm):
        return alarm[AodhProps.NAME]

    def _get_alarms(self):
        try:
            aodh_alarms = self.client.alarms.list()
            return [self._convert_alarm(alarm) for alarm in aodh_alarms]
        except Exception as e:
                LOG.exception("Exception: %s", e)
        return []

    def _is_erroneous(self, alarm):
        return alarm and alarm[AodhProps.STATE] == AodhState.ALARM

    def _status_changed(self, alarm1, alarm2):
        return alarm1 and alarm2 and \
            not alarm1[AodhProps.STATE] == alarm2[AodhProps.STATE]

    def _is_valid(self, alarm):
        return True

    @classmethod
    def _convert_event_alarm(cls, alarm):
        res = cls._convert_base_alarm(alarm)
        res[AodhProps.EVENT_TYPE] = alarm.event_rule[AodhProps.EVENT_TYPE],
        res[AodhProps.RESOURCE_ID] = _parse_query(alarm.event_rule,
                                                  AodhProps.EVENT_RESOURCE_ID)
        return res

    @classmethod
    def _convert_threshold_alarm(cls, alarm):
        res = cls._convert_base_alarm(alarm)
        res[AodhProps.STATE_TIMESTAMP] = alarm.state_timestamp
        res[AodhProps.RESOURCE_ID] = _parse_query(alarm.threshold_rule,
                                                  AodhProps.RESOURCE_ID)
        return res

    @classmethod
    def _convert_vitrage_alarm(cls, alarm):
        res = cls._convert_base_alarm(alarm)
        res[AodhProps.VITRAGE_ID] = _parse_query(alarm.event_rule,
                                                 AodhProps.VITRAGE_ID)
        res[AodhProps.RESOURCE_ID] = _parse_query(alarm.event_rule,
                                                  AodhProps.RESOURCE_ID)
        return res

    @staticmethod
    def _convert_base_alarm(alarm):
        # TODO(iafek): what if the alarm state is 'insufficient data'

        return {
            AodhProps.DESCRIPTION: alarm.description,
            AodhProps.ENABLED: alarm.enabled,
            AodhProps.ALARM_ID: alarm.alarm_id,
            AodhProps.NAME: alarm.name,
            AodhProps.PROJECT_ID: alarm.project_id,
            AodhProps.REPEAT_ACTIONS: alarm.repeat_actions,
            AodhProps.SEVERITY: alarm.severity,
            AodhProps.STATE: alarm.state,
            AodhProps.TIMESTAMP: alarm.timestamp,
            AodhProps.TYPE: alarm.type
        }

    @classmethod
    def _convert_alarm(cls, alarm):
        alarm_type = alarm.type
        if alarm_type == AodhProps.EVENT and _is_vitrage_alarm(alarm):
            return cls._convert_vitrage_alarm(alarm)
        elif alarm_type == AodhProps.EVENT:
            return cls._convert_event_alarm(alarm)
        elif alarm_type == AodhProps.THRESHOLD:
            return cls._convert_threshold_alarm(alarm)
        else:
            LOG.warning('Unsupported Aodh alarm of type %s' % alarm_type)


def _parse_query(data, key):
    query_fields = data.get(AodhProps.QUERY, {})
    for query in query_fields:
        field = query['field']
        if field == key:
            return query['value']
    return None


def _is_vitrage_alarm(alarm):
    return _parse_query(alarm.event_rule, AodhProps.VITRAGE_ID) is not None
