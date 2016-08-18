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

from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EdgeProperties as EProps
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EventAction
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common.exception import VitrageTransformerError
from vitrage.datasources import transformer_base
from vitrage.datasources.transformer_base import Neighbor
from vitrage.evaluator.actions.recipes.action_steps import ADD_EDGE
from vitrage.evaluator.actions.recipes.action_steps import ADD_VERTEX
from vitrage.evaluator.actions.recipes.action_steps import REMOVE_EDGE
from vitrage.evaluator.actions.recipes.action_steps import REMOVE_VERTEX
from vitrage.evaluator.actions.recipes.action_steps import UPDATE_VERTEX
from vitrage.evaluator.actions.recipes.base import EVALUATOR_EVENT_TYPE
from vitrage.evaluator.template_fields import TemplateFields as TFields
import vitrage.graph.utils as graph_utils
from vitrage.graph import Vertex


LOG = logging.getLogger(__name__)


VITRAGE_TYPE = 'vitrage'


class EvaluatorEventTransformer(transformer_base.TransformerBase):

    def __init__(self, transformers, conf):
        super(EvaluatorEventTransformer, self).__init__(transformers, conf)
        self.actions = self._init_actions()

    def _create_snapshot_entity_vertex(self, entity_event):
        return self._create_vertex(entity_event)

    def _create_update_entity_vertex(self, entity_event):
        return self._create_vertex(entity_event)

    def _create_vertex(self, event):

        event_type = event[EVALUATOR_EVENT_TYPE]

        update_timestamp = transformer_base.convert_timestamp_format(
            '%Y-%m-%d %H:%M:%S.%f',
            event[VProps.UPDATE_TIMESTAMP]
        )

        if event_type == UPDATE_VERTEX:
            properties = {
                VProps.VITRAGE_STATE: event.get(VProps.VITRAGE_STATE),
                VProps.IS_MARKED_DOWN: event.get(VProps.IS_MARKED_DOWN),
                VProps.UPDATE_TIMESTAMP: update_timestamp,
                VProps.SAMPLE_TIMESTAMP: event[VProps.SAMPLE_TIMESTAMP],
                VProps.IS_PLACEHOLDER: False
            }
            return Vertex(event[VProps.VITRAGE_ID], properties)

        if event_type in [ADD_VERTEX, REMOVE_VERTEX]:

            metadata = {
                VProps.NAME: event[TFields.ALARM_NAME],
                VProps.SEVERITY: event[TFields.SEVERITY],
                VProps.STATE: event[VProps.STATE]
            }
            return graph_utils.create_vertex(
                self._create_entity_key(event),
                entity_category=EntityCategory.ALARM,
                entity_type=VITRAGE_TYPE,
                sample_timestamp=event[VProps.SAMPLE_TIMESTAMP],
                update_timestamp=update_timestamp,
                metadata=metadata)

        return None

    def _create_snapshot_neighbors(self, event):
        return self._create_vitrage_neighbors(event)

    def _create_update_neighbors(self, event):
        return self._create_vitrage_neighbors(event)

    def _create_vitrage_neighbors(self, event):
        event_type = event[EVALUATOR_EVENT_TYPE]

        timestamp = transformer_base.convert_timestamp_format(
            '%Y-%m-%d %H:%M:%S.%f',
            event[VProps.UPDATE_TIMESTAMP]
        )

        if event_type in [ADD_EDGE, REMOVE_EDGE]:

            relation_edge = graph_utils.create_edge(
                source_id=event[TFields.SOURCE],
                target_id=event[TFields.TARGET],
                relationship_type=event[EProps.RELATIONSHIP_TYPE],
                update_timestamp=timestamp)

            return [Neighbor(None, relation_edge)]

        if event_type == ADD_VERTEX:

            relation_edge = graph_utils.create_edge(
                source_id=self._create_entity_key(event),
                target_id=event[TFields.TARGET],
                relationship_type=EdgeLabel.ON,
                update_timestamp=timestamp)

            neighbor_props = {
                VProps.IS_PLACEHOLDER: True,
                VProps.UPDATE_TIMESTAMP: timestamp,
                VProps.SAMPLE_TIMESTAMP: event[VProps.SAMPLE_TIMESTAMP]
            }
            neighbor = Vertex(event[TFields.TARGET], neighbor_props)
            return [Neighbor(neighbor, relation_edge)]

        return []

    def _extract_action_type(self, event):
        event_type = event[EVALUATOR_EVENT_TYPE]

        try:
            return self.actions[event_type]
        except Exception:
            raise VitrageTransformerError(
                'Invalid Evaluator event type: (%s)' % event_type)

    @staticmethod
    def _init_actions():
        return {
            UPDATE_VERTEX: EventAction.UPDATE_ENTITY,
            ADD_VERTEX: EventAction.CREATE_ENTITY,
            REMOVE_VERTEX: EventAction.DELETE_ENTITY,
            ADD_EDGE: EventAction.UPDATE_RELATIONSHIP,
            REMOVE_EDGE: EventAction.DELETE_RELATIONSHIP
        }

    def _create_entity_key(self, event):
        key_fields = self._key_values(event[TFields.ALARM_NAME],
                                      event[TFields.TARGET])
        return transformer_base.build_key(key_fields)

    def _key_values(self, *args):
        return (EntityCategory.ALARM, VITRAGE_TYPE) + args

    def create_placeholder_vertex(self, **kwargs):
        LOG.info('Evaluator does not create placeholders')

    def get_type(self):
        return VITRAGE_TYPE
