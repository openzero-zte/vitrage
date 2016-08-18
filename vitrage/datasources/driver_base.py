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

import abc
import six

from oslo_log import log

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common import datetime_utils

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class DriverBase(object):

    def __init__(self):
        pass

    @abc.abstractmethod
    def get_all(self, sync_mode):
        pass

    @staticmethod
    def _get_end_message(sync_type):
        end_message = {
            DSProps.SYNC_TYPE: sync_type,
            DSProps.SYNC_MODE: SyncMode.INIT_SNAPSHOT,
            DSProps.EVENT_TYPE: EventAction.END_MESSAGE
        }
        return end_message

    def get_changes(self, sync_mode):
        pass

    @classmethod
    def make_pickleable(cls, entities, sync_type, sync_mode, *args):
        pickleable_entities = []

        for entity in entities:
            for field in args:
                entity.pop(field, None)

            cls._add_sync_type(entity, sync_type)
            cls._add_sync_mode(entity, sync_mode)
            cls._add_sampling_time(entity)
            pickleable_entities.append(entity)

        if sync_mode == SyncMode.INIT_SNAPSHOT:
            pickleable_entities.append(cls._get_end_message(sync_type))

        return pickleable_entities

    @staticmethod
    def _add_sync_type(entity, sync_type):
        if DSProps.SYNC_TYPE not in entity:
            entity[DSProps.SYNC_TYPE] = sync_type

    @staticmethod
    def _add_sampling_time(entity):
        entity[DSProps.SAMPLE_DATE] = str(datetime_utils.utcnow())

    @staticmethod
    def _add_sync_mode(entity, sync_mode):
        entity[DSProps.SYNC_MODE] = sync_mode

    @staticmethod
    @abc.abstractmethod
    def enrich_event(event, event_type):
        """Return the given event with extra fields

        We add extra data, which the transformer uses later on.
        For example, we can add a timestamp and change the message's structure
        :param event: the event received by oslo
        :param event_type: the event type of the event
        :return: the enriched event
        """

        pass

    @staticmethod
    @abc.abstractmethod
    def get_event_types(conf):
        """Return a list of all event types relevant to this datasource

        Example:
        return ['compute.instance.update',
                'compute.instance.resume']

        It also supports prefixes- the event types which start
        with this prefix will be processed by this driver:
        Example:
        return ['compute.instance']



        :return: a list of event types
        :rtype: list of str
        """

        return []
