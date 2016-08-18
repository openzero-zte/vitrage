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
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EventAction
from vitrage.common.constants import SyncMode
from vitrage.common.exception import VitrageTransformerError
from vitrage.datasources.alarm_properties import AlarmProperties as AlarmProps
from vitrage.datasources import transformer_base as tbase

LOG = logging.getLogger(__name__)


class AlarmTransformerBase(tbase.TransformerBase):

    def __init__(self, transformers, conf):
        super(AlarmTransformerBase, self).__init__(transformers, conf)

    def _ok_status(self, entity_event):
        pass

    def create_placeholder_vertex(self, **kwargs):
        LOG.info('An alarm cannot be a placeholder')
        pass

    def _extract_action_type(self, entity_event):
        # TODO(ifat_afek): this method should reside together with the cache,
        # in the transformer code
        if DSProps.EVENT_TYPE in entity_event and \
           entity_event[DSProps.EVENT_TYPE] == EventAction.DELETE_ENTITY:
            return entity_event[DSProps.EVENT_TYPE]

        sync_mode = entity_event[DSProps.SYNC_MODE]
        if sync_mode in (SyncMode.UPDATE, SyncMode.SNAPSHOT):
            return EventAction.DELETE_ENTITY if self._ok_status(entity_event) \
                else EventAction.UPDATE_ENTITY

        if SyncMode.INIT_SNAPSHOT == sync_mode:
            return EventAction.CREATE_ENTITY

        raise VitrageTransformerError('Invalid sync mode: (%s)' % sync_mode)

    def _key_values(self, *args):
        return (EntityCategory.ALARM,) + args

    def _get_alarm_state(self, entity_event):
        event_type = entity_event.get(DSProps.EVENT_TYPE, None)
        if event_type is not None:
            return AlarmProps.INACTIVE_STATE if \
                EventAction.DELETE_ENTITY == event_type else \
                AlarmProps.ACTIVE_STATE
        else:
            return AlarmProps.INACTIVE_STATE if \
                self._ok_status(entity_event) else \
                AlarmProps.ACTIVE_STATE
