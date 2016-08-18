# Copyright 2016 - Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log
from six.moves import reduce
from vitrage.evaluator.actions.base import ActionType
from vitrage.evaluator.template_data import TemplateData
from vitrage.evaluator.template_fields import TemplateFields
from vitrage.evaluator.template_validation.base import get_correct_result
from vitrage.evaluator.template_validation.base import get_fault_result
from vitrage.evaluator.template_validation.status_messages import status_msgs

LOG = log.getLogger(__name__)


RESULT_DESCRIPTION = 'Template content validation'


def content_validation(template):

    template_definitions = template[TemplateFields.DEFINITIONS]

    entity_ids = []
    entities = template_definitions[TemplateFields.ENTITIES]
    result = validate_entities_definition(entities, entity_ids)

    relationship_ids = []

    if result.is_valid and \
       TemplateFields.RELATIONSHIPS in template_definitions:

        relationships = template_definitions[TemplateFields.RELATIONSHIPS]
        result = validate_relationships_definitions(relationships,
                                                    relationship_ids,
                                                    entity_ids)
    if result.is_valid:
        scenarios = template[TemplateFields.SCENARIOS]
        template_ids = entity_ids + relationship_ids
        result = validate_scenarios(scenarios, template_ids)

    return result


def validate_entities_definition(entities, entity_ids):

    for entity in entities:

        entity_dict = entity[TemplateFields.ENTITY]
        result = validate_entity_definition(entity_dict, entity_ids)

        if not result.is_valid:
            return result

        entity_ids.append(entity_dict[TemplateFields.TEMPLATE_ID])

    return get_correct_result(RESULT_DESCRIPTION)


def validate_entity_definition(entity, entities_ids):

    template_id = entity[TemplateFields.TEMPLATE_ID]
    if template_id in entities_ids:
        LOG.error('%s status code: %s' % (status_msgs[2], 2))
        return get_fault_result(RESULT_DESCRIPTION, 2)

    return get_correct_result(RESULT_DESCRIPTION)


def validate_relationships_definitions(relationships,
                                       relationship_ids,
                                       entity_ids):

    for relationship in relationships:

        relationship_dict = relationship[TemplateFields.RELATIONSHIP]
        result = validate_relationship(relationship_dict,
                                       relationship_ids,
                                       entity_ids)
        if not result.is_valid:
            return result

        relationship_ids.append(relationship_dict[TemplateFields.TEMPLATE_ID])
    return get_correct_result(RESULT_DESCRIPTION)


def validate_relationship(relationship, relationships_ids, entities_ids):

    template_id = relationship[TemplateFields.TEMPLATE_ID]
    if template_id in (entities_ids or relationships_ids):
        LOG.error('%s status code: %s' % (status_msgs[2], 2))
        return get_fault_result(RESULT_DESCRIPTION, 2)

    target = relationship[TemplateFields.TARGET]
    result = _validate_template_id(entities_ids, target)

    if result.is_valid:
        source = relationship[TemplateFields.SOURCE]
        result = _validate_template_id(entities_ids, source)

    return result


def validate_scenarios(scenarios, template_ids):

    for scenario in scenarios:

        scenario_values = scenario[TemplateFields.SCENARIO]

        condition = scenario_values[TemplateFields.CONDITION]
        result = validate_scenario_condition(condition, template_ids)

        if not result.is_valid:
            return result

        actions = scenario_values[TemplateFields.ACTIONS]
        result = validate_scenario_actions(actions, template_ids)

        if not result.is_valid:
            return result

    return get_correct_result(RESULT_DESCRIPTION)


def validate_scenario_condition(condition, template_ids):

    try:
        TemplateData.convert_to_dnf_format(condition)
    except Exception:
        LOG.error('%s status code: %s' % (status_msgs[85], 85))
        return get_fault_result(RESULT_DESCRIPTION, 85)

    values_to_replace = ' and ', ' or ', ' not ', '(', ')'
    condition = reduce(lambda cond, v: cond.replace(v, ' '),
                       values_to_replace,
                       condition)

    for condition_var in condition.split(' '):

        if len(condition_var.strip()) == 0:
            continue

        result = _validate_template_id(template_ids, condition_var)
        if not result.is_valid:
            return result

    return get_correct_result(RESULT_DESCRIPTION)


def validate_scenario_actions(actions, entities_ids):

    for action in actions:
        result = validate_scenario_action(action[TemplateFields.ACTION],
                                          entities_ids)
        if not result.is_valid:
            return result

    return get_correct_result(RESULT_DESCRIPTION)


def validate_scenario_action(action, entities_ids):

    action_type = action[TemplateFields.ACTION_TYPE]
    actions = {
        ActionType.RAISE_ALARM: validate_raise_alarm_action,
        ActionType.SET_STATE: validate_set_state_action,
        ActionType.ADD_CAUSAL_RELATIONSHIP:
        validate_add_causal_relationship_action,
        ActionType.MARK_DOWN: validate_mark_down_action,
    }

    if action_type not in actions.keys():
        LOG.error('%s status code: %s' % (status_msgs[120], 120))
        return get_fault_result(RESULT_DESCRIPTION, 120)

    return actions[action_type](action, entities_ids)


def validate_raise_alarm_action(action, entities_ids):

    properties = action[TemplateFields.PROPERTIES]

    if TemplateFields.ALARM_NAME not in properties:
        LOG.error('%s status code: %s' % (status_msgs[125], 125))
        return get_fault_result(RESULT_DESCRIPTION, 125)

    if TemplateFields.SEVERITY not in properties:
        LOG.error('%s status code: %s' % (status_msgs[126], 126))
        return get_fault_result(RESULT_DESCRIPTION, 126)

    action_target = action[TemplateFields.ACTION_TARGET]
    if TemplateFields.TARGET not in action_target:
        LOG.error('%s status code: %s' % (status_msgs[127], 127))
        return get_fault_result(RESULT_DESCRIPTION, 127)

    target = action_target[TemplateFields.TARGET]
    return _validate_template_id(entities_ids, target)


def validate_set_state_action(action, entities_ids):

    properties = action[TemplateFields.PROPERTIES]

    if TemplateFields.STATE not in properties:
        LOG.error('%s status code: %s' % (status_msgs[128], 128))
        return get_fault_result(RESULT_DESCRIPTION, 128)

    action_target = action[TemplateFields.ACTION_TARGET]
    if TemplateFields.TARGET not in action_target:
        LOG.error('%s status code: %s' % (status_msgs[129], 129))
        return get_fault_result(RESULT_DESCRIPTION, 129)

    target = action_target[TemplateFields.TARGET]
    return _validate_template_id(entities_ids, target)


def validate_add_causal_relationship_action(action, entities_ids):

    action_target = action[TemplateFields.ACTION_TARGET]

    if TemplateFields.TARGET not in action_target:
        LOG.error('%s status code: %s' % (status_msgs[130], 130))
        return get_fault_result(RESULT_DESCRIPTION, 130)

    target = action_target[TemplateFields.TARGET]
    result = _validate_template_id(entities_ids, target)

    if not result.is_valid:
        return result

    if TemplateFields.SOURCE not in action_target:
        LOG.error('%s status code: %s' % (status_msgs[130], 130))
        return get_fault_result(RESULT_DESCRIPTION, 130)

    source = action_target[TemplateFields.SOURCE]
    return _validate_template_id(entities_ids, source)


def validate_mark_down_action(action, entities_ids):

    action_target = action[TemplateFields.ACTION_TARGET]
    if TemplateFields.TARGET not in action_target:
        LOG.error('%s status code: %s' % (status_msgs[131], 131))
        return get_fault_result(RESULT_DESCRIPTION, 131)

    target = action_target[TemplateFields.TARGET]
    return _validate_template_id(entities_ids, target)


def _validate_template_id(ids, id_to_check):

    if id_to_check not in ids:
        msg = status_msgs[3] + ' template id: %s' % id_to_check
        LOG.error('%s status code: %s' % (msg, 3))
        return get_fault_result(RESULT_DESCRIPTION, 3, msg)

    return get_correct_result(RESULT_DESCRIPTION)
