# Copyright 2015 - Alcatel-Lucent
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

import abc
from collections import namedtuple

from oslo_log import log as logging
import six
from vitrage.common import datetime_utils

import vitrage.common.constants as cons
from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common.constants import UpdateMethod
from vitrage.common.exception import VitrageTransformerError
from vitrage.common import utils
from vitrage.datasources import OPENSTACK_CLUSTER
import vitrage.graph.utils as graph_utils

LOG = logging.getLogger(__name__)

EntityWrapper = \
    namedtuple('EntityWrapper', ['vertex', 'neighbors', 'action'])

Neighbor = namedtuple('Neighbor', ['vertex', 'edge'])


TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


AVAILABLE = 'available'


def extract_field_value(entity_event, *args):
    try:
        value = entity_event
        for key in args:
            value = value[key]

        return value
    except Exception:
        return None


def build_key(key_values):
    return TransformerBase.KEY_SEPARATOR.join(map(str, key_values))


def create_cluster_placeholder_vertex():
    key = build_key([cons.EntityCategory.RESOURCE,
                     OPENSTACK_CLUSTER])

    metadata = {
        cons.VertexProperties.NAME: OPENSTACK_CLUSTER
    }

    return graph_utils.create_vertex(
        key,
        entity_id=OPENSTACK_CLUSTER,
        entity_category=cons.EntityCategory.RESOURCE,
        entity_type=OPENSTACK_CLUSTER,
        entity_state=AVAILABLE,
        metadata=metadata
    )


def convert_timestamp_format(current_timestamp_format, timestamp):

    return datetime_utils.change_time_str_format(
        timestamp,
        current_timestamp_format,
        TIMESTAMP_FORMAT
    )


def is_update_event(event):
    return event[DSProps.SYNC_MODE] == SyncMode.UPDATE


@six.add_metaclass(abc.ABCMeta)
class TransformerBase(object):

    KEY_SEPARATOR = ':'
    QUERY_RESULT = 'graph_query_result'

    UPDATE_EVENT_TYPES = {}

    def __init__(self, transformers, conf):
        self.conf = conf
        self.transformers = transformers

    def transform(self, entity_event):
        """Transform an entity event into entity wrapper.

        Entity event is received from driver and it need to be
        transformed into entity wrapper. The wrapper contains:
            1. Entity Vertex - The vertex itself with all fields
            2. Neighbor list - neighbor placeholder vertex and an edge
            3. Action type - CREATE/UPDATE/DELETE

        :param entity_event: a general event from the driver
        :return: entity wrapper
        :rtype:EntityWrapper
        """

        if not self._is_end_message(entity_event):
            entity_vertex = self._create_entity_vertex(entity_event)
            neighbors = self._create_neighbors(entity_event)
            action = self._extract_action_type(entity_event)

            return EntityWrapper(entity_vertex, neighbors, action)
        else:
            return EntityWrapper(self._create_end_vertex(entity_event),
                                 None,
                                 EventAction.END_MESSAGE)

    def _create_entity_vertex(self, entity_event):
        if is_update_event(entity_event) and \
                utils.opt_exists(self.conf, self.get_type()) and \
                utils.opt_exists(self.conf[self.get_type()], 'update_method'):
            update_method = self.conf[self.get_type()].update_method.lower()
            if update_method == UpdateMethod.PUSH:
                return self._create_update_entity_vertex(entity_event)
            elif update_method == UpdateMethod.PULL:
                return self._create_snapshot_entity_vertex(entity_event)
            elif update_method == UpdateMethod.NONE:
                return None
            else:
                LOG.error('Update event arrived for dataresource that is '
                          'defined without updates')
        else:
            return self._create_snapshot_entity_vertex(entity_event)

    @abc.abstractmethod
    def _create_snapshot_entity_vertex(self, entity_event):
        pass

    @abc.abstractmethod
    def _create_update_entity_vertex(self, entity_event):
        pass

    def _create_neighbors(self, entity_event):
        """Extracts entity neighbors received from a given entity event.

         Extracting entity neighbors from a given event provided
         by driver

         :param entity_event: an event provided by driver
         :return: neighbors - a list of neighbors where each item in the list
                              is a tuple of (vertex, edge)
         :rtype: list
         """

        if is_update_event(entity_event):
            return self._create_update_neighbors(entity_event)
        else:
            return self._create_snapshot_neighbors(entity_event)

    def _create_snapshot_neighbors(self, entity_event):
        return []

    def _create_update_neighbors(self, entity_event):
        return []

    @abc.abstractmethod
    def _create_entity_key(self, entity_event):
        """Create entity key from given event

        By given an entity event, return a entity key which
        consisting key fields

        :param entity_event: event that returns from the driver
        :return: key
        """
        pass

    @abc.abstractmethod
    def create_placeholder_vertex(self, **kwargs):
        """Creates placeholder vertex.

        Placeholder vertex contains only mandatory fields of this entity.
        This way other datasources can create placeholder vertices of those
        entities

        :param kwargs: the properties for the placeholder vertex
        :return: Placeholder vertex
        :rtype: Vertex
        """
        pass

    def _extract_action_type(self, entity_event):
        """Extract action type.

        Decides what action (from constants.EventAction) the processor need
        to perform according to the data received from the event.

        :param entity_event: event that returns from the driver
        :return: the action that the processor needs to perform
        :rtype: str
        """

        sync_mode = entity_event[DSProps.SYNC_MODE]

        if SyncMode.UPDATE == sync_mode:
            return self.UPDATE_EVENT_TYPES.get(
                entity_event.get(DSProps.EVENT_TYPE, None),
                EventAction.UPDATE_ENTITY)

        if SyncMode.SNAPSHOT == sync_mode:
            return EventAction.UPDATE_ENTITY

        if SyncMode.INIT_SNAPSHOT == sync_mode:
            return EventAction.CREATE_ENTITY

        raise VitrageTransformerError(
            'Invalid sync mode: (%s)' % sync_mode)

    def _key_values(self, *args):
        """A list of key fields

        The fields which consist the entity key

        :param args: a tuple of mutable key fields
        :return: ()
        """
        pass

    @staticmethod
    def _create_end_vertex(entity_event):
        sync_type = entity_event[DSProps.SYNC_TYPE]
        return graph_utils.create_vertex(
            'END_MESSAGE:' + sync_type,
            entity_type=sync_type)

    @staticmethod
    def _is_end_message(entity_event):

        sync_mode = entity_event[DSProps.SYNC_MODE]
        is_snapshot_event = sync_mode == SyncMode.INIT_SNAPSHOT
        event_type = entity_event.get(DSProps.EVENT_TYPE, None)
        return is_snapshot_event and event_type == EventAction.END_MESSAGE

    @staticmethod
    def _format_update_timestamp(update_timestamp, sample_timestamp):
        return update_timestamp if update_timestamp else sample_timestamp

    @staticmethod
    def get_enrich_query(event):
        """Allow running a query on the graph vertices

        The result of the query specified here will be added to the event in
        the 'QUERY_RESULT' field.

         Example:
         -------
          query = {'type': 'nova.instance'}
          Before transform is called the result of running the query against
          the topology graph will be updated to event[QUERY_RESULT]
          To contain the list of all the vertices with type=nova.instance
        """
        return None

    @abc.abstractmethod
    def get_type(self):
        """Returns the type of the datasource

        :return: datasource type
        :rtype: String
        """
        pass
