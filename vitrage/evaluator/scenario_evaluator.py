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

from collections import namedtuple

from oslo_log import log

from vitrage.common.constants import EdgeProperties as EProps
from vitrage.common.constants import VertexProperties as VProps
from vitrage.entity_graph.mappings.datasource_info_mapper \
    import DatasourceInfoMapper
from vitrage.evaluator.actions.action_executor import ActionExecutor
from vitrage.evaluator.actions.base import ActionMode
from vitrage.evaluator.actions.base import ActionType
import vitrage.evaluator.actions.priority_tools as pt
from vitrage.evaluator.template_data import ActionSpecs
from vitrage.evaluator.template_data import EdgeDescription
from vitrage.evaluator.template_data import ENTITY
from vitrage.graph.algo_driver.algorithm import Mapping
from vitrage.graph import create_algorithm
from vitrage.graph import create_graph
from vitrage.graph.driver import Vertex

LOG = log.getLogger(__name__)

# Entry containing action info.
# specs - ActionSpecs
# mode - DO or UNDO (the action)
# scenario_id - the scenario id in scenario_repository
# Trigger_id  - a unique identifier per match in graph (i.e., the subgraph
# that matched the action in the spec) for the specific action.
ActionInfo = \
    namedtuple('ActionInfo', ['specs', 'mode', 'scenario_id', 'trigger_id'])


class ScenarioEvaluator(object):

    def __init__(self,
                 conf,
                 entity_graph,
                 scenario_repo,
                 event_queue,
                 enabled=False):
        self.conf = conf
        self._scenario_repo = scenario_repo
        self._entity_graph = entity_graph
        self._graph_algs = create_algorithm(entity_graph)
        self._action_executor = ActionExecutor(event_queue)
        self._entity_graph.subscribe(self.process_event)
        self._action_tracker = ActionTracker(DatasourceInfoMapper(self.conf))
        self.enabled = enabled

    @property
    def scenario_repo(self):
        return self._scenario_repo

    @scenario_repo.setter
    def scenario_repo(self, scenario_repo):
        self._scenario_repo = scenario_repo

    def process_event(self, before, current, is_vertex):
        """Notification of a change in the entity graph.

        :param is_vertex:
        :param before: The graph element (vertex or edge) prior to the
        change that happened. None if the element was just created.
        :param current: The graph element (vertex or edge) after the
        change that happened. Deleted elements should arrive with the
        is_deleted property set to True
        """

        if not self.enabled:
            LOG.debug("Process event disabled")
            return

        LOG.debug('Process event - starting')
        LOG.debug("Element before event: %s, Current element: %s",
                  str(before),
                  str(current))

        # todo (erosensw): support for NOT conditions - reverse logic
        before_scenarios = self._get_element_scenarios(before, is_vertex)
        current_scenarios = self._get_element_scenarios(current, is_vertex)
        before_scenarios, current_scenarios = \
            self._remove_overlap_scenarios(before_scenarios, current_scenarios)

        if len(before_scenarios) + len(current_scenarios):
            LOG.debug("Number of relevant scenarios found: undo = %s, do = %s",
                      str(len(before_scenarios)),
                      str(len(current_scenarios)))

        actions = self._process_and_get_actions(before,
                                                before_scenarios,
                                                ActionMode.UNDO)
        actions.update(self._process_and_get_actions(current,
                                                     current_scenarios,
                                                     ActionMode.DO))

        if actions:
            LOG.debug("Actions to perform: %s", actions.values())
            filtered_actions = \
                self._analyze_and_filter_actions(actions.values())
            LOG.debug("Actions after filter: %s", filtered_actions.values())
            for action in filtered_actions:
                self._action_executor.execute(action.specs, action.mode)

        LOG.debug('Process event - completed')

    def _get_element_scenarios(self, element, is_vertex):
        if not element \
                or element.get(VProps.IS_DELETED) \
                or element.get(EProps.IS_DELETED):
            return []
        elif is_vertex:
            return self._scenario_repo.get_scenarios_by_vertex(element)
        else:  # is edge
            edge_desc = self._get_edge_description(element)
            return self._scenario_repo.get_scenarios_by_edge(edge_desc)

    def _get_edge_description(self, element):
        source = self._entity_graph.get_vertex(element.source_id)
        target = self._entity_graph.get_vertex(element.target_id)
        edge_desc = EdgeDescription(element, source, target)
        return edge_desc

    @staticmethod
    def _remove_overlap_scenarios(before, current):
        intersection = list(filter(lambda x: x in before, current))
        before = list(filter(lambda x: x not in intersection, before))
        current = list(filter(lambda x: x not in intersection, current))
        return before, current

    def _process_and_get_actions(self, element, triggered_scenarios, mode):
        actions = {}
        for triggered_scenario in triggered_scenarios:
            LOG.debug("Processing: %s", str(triggered_scenario))
            scenario_element = triggered_scenario[0]
            scenario = triggered_scenario[1]
            actions.update(self._process_scenario(element,
                                                  scenario,
                                                  scenario_element,
                                                  mode))
        return actions

    def _process_scenario(self, element, scenario, scenario_elements, mode):
        if not isinstance(scenario_elements, list):
            scenario_elements = [scenario_elements]
        actions = {}
        for action in scenario.actions:
            for scenario_element in scenario_elements:
                matches = self._evaluate_full_condition(scenario.condition,
                                                        element,
                                                        scenario_element)
                if matches:
                    for match in matches:
                        spec, action_id = self._get_action_spec(action, match)
                        match_hash = hash(tuple(sorted(match.items())))
                        actions[action_id] = \
                            ActionInfo(spec, mode, scenario.id, match_hash)
        return actions

    @staticmethod
    def _get_action_spec(action_spec, match):
        targets = action_spec.targets
        real_items = {
            target: match[target_id] for target, target_id in targets.items()
        }
        revised_spec = ActionSpecs(action_spec.type,
                                   real_items,
                                   action_spec.properties)
        # noinspection PyTypeChecker
        action_id = ScenarioEvaluator._generate_action_id(revised_spec)
        return revised_spec, action_id

    @staticmethod
    def _generate_action_id(action_spec):
        targets = [(k, v.vertex_id) for k, v in action_spec.targets.items()]
        return hash(
            (action_spec.type,
             tuple(sorted(targets)),
             tuple(sorted(action_spec.properties.items())))
        )

    def _evaluate_full_condition(self, condition, element, scenario_element):
        condition_matches = []
        for clause in condition:
            # OR condition means aggregation of matches, without duplicates
            and_condition_matches = \
                self._evaluate_and_condition(clause, element, scenario_element)
            condition_matches += and_condition_matches

        return condition_matches

    def _evaluate_and_condition(self, condition, element, scenario_element):

        condition_g = create_graph("scenario condition")
        for term in condition:
            if not term.positive:
                # todo(erosensw): add support for NOT clauses
                LOG.error('Template with NOT operator current not supported')
                return []

            if term.type == ENTITY:
                term.variable[VProps.IS_DELETED] = False
                condition_g.add_vertex(term.variable)

            else:  # type = relationship
                edge_desc = term.variable
                self._set_relationship_not_deleted(edge_desc)
                self._add_relationship(condition_g, edge_desc)

        if isinstance(element, Vertex):
            initial_map = Mapping(scenario_element, element, True)
        else:
            initial_map = Mapping(scenario_element.edge, element, False)
        return self._graph_algs.sub_graph_matching(condition_g, [initial_map])

    @staticmethod
    def _set_relationship_not_deleted(edge_description):
        edge_description.source[VProps.IS_DELETED] = False
        edge_description.target[VProps.IS_DELETED] = False
        edge_description.edge[EProps.IS_DELETED] = False

    @staticmethod
    def _add_relationship(condition_graph, edge_description):
        condition_graph.add_vertex(edge_description.source)
        condition_graph.add_vertex(edge_description.target)
        condition_graph.add_edge(edge_description.edge)

    def _analyze_and_filter_actions(self, actions):

        actions_to_perform = {}
        for action in actions:
            key = self._action_tracker.get_key(action.specs)
            prev_dominant = self._action_tracker.get_dominant_action(key)
            if action.mode == ActionMode.DO:
                self._action_tracker.insert_action(key, action)
            else:
                self._action_tracker.remove_action(key, action)
            new_dominant = self._action_tracker.get_dominant_action(key)

            # todo: (erosensw) improvement - first analyze DOs, then UNDOs
            if not new_dominant:  # removed last entry for key
                undo_action = ActionInfo(prev_dominant.specs,
                                         ActionMode.UNDO,
                                         prev_dominant.scenario_id,
                                         prev_dominant.trigger_id)
                actions_to_perform[key] = undo_action
            elif new_dominant != prev_dominant:
                actions_to_perform[key] = new_dominant
        return actions_to_perform.values()


class ActionTracker(object):
    """Keeps track of all active actions and relative dominance/priority.

    Actions are organized according to resource-id
    and action details.
    Examples:
    - all set_state actions on a given resource share the same entry,
    regardless of state
    - all raise_alarm of type alarm_name on a given resource share the same
     entry, regardless of severity
    """

    def __init__(self, datasource_info_mapper):
        self._tracker = {}
        alarms_score = \
            datasource_info_mapper.get_datasource_priorities('vitrage')
        all_scores = datasource_info_mapper.get_datasource_priorities()
        self._action_tools = {
            ActionType.SET_STATE: pt.SetStateTools(all_scores),
            ActionType.RAISE_ALARM: pt.RaiseAlarmTools(alarms_score),
            ActionType.ADD_CAUSAL_RELATIONSHIP: pt.BaselineTools,
            ActionType.MARK_DOWN: pt.BaselineTools
        }

    def get_key(self, action_specs):
        return self._action_tools[action_specs.type].get_key(action_specs)

    def insert_action(self, key, action):
        actions = self._tracker.get(key, [])
        actions.append(action)
        scorer = self._action_tools[action.specs.type].get_score
        self._tracker[key] = sorted(actions, key=scorer, reverse=True)

    def remove_action(self, key, action):
        # actions are unique in their trigger and scenario_ids
        def _is_equivalent(entry):
            return entry.trigger_id == action.trigger_id and \
                entry.scenario_id == action.scenario_id
        try:
            to_remove = next(entry for entry in self._tracker[key]
                             if _is_equivalent(entry))
            self._tracker[key].remove(to_remove)
        except StopIteration:
            LOG.warning("Could not find action entry to remove "
                        "from tracker: {}".format(action))

    def get_dominant_action(self, key):
        return self._tracker[key][0] if self._tracker.get(key, None) else None
