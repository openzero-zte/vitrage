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
import copy
import logging

from oslo_log import log

from vitrage.common import file_utils
from vitrage.evaluator.actions.base import ActionType
from vitrage.evaluator.template_fields import TemplateFields
from vitrage.evaluator.template_validation.status_messages import status_msgs
from vitrage.evaluator.template_validation import template_content_validator \
    as validator
from vitrage.tests import base
from vitrage.tests.mocks import utils

LOG = log.getLogger(__name__)


class TemplateContentValidatorTest(base.BaseTest):

    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls):

        template_dir_path = '%s/templates/general' % utils.get_resources_dir()
        cls.templates = file_utils.load_yaml_files(template_dir_path)
        cls.first_template = cls.templates[0]

        cls._hide_useless_logging_messages()

    @property
    def clone_template(self):
        return copy.deepcopy(self.first_template)

    def test_template_validator(self):
        for template in self.templates:
            self._test_execute_and_assert_with_correct_result(template)

    def test_validate_entity_definition_with_no_unique_template_id(self):

        template = self.clone_template
        definitions = template[TemplateFields.DEFINITIONS]

        for entity in definitions[TemplateFields.ENTITIES]:
            entity_dict = entity[TemplateFields.ENTITY]
            entity_dict[TemplateFields.TEMPLATE_ID] = 'aaa'

        self._test_execute_and_assert_with_fault_result(template, 2)

    def test_validate_relationship_with_no_unique_template_id(self):

        template = self.clone_template
        definitions = template[TemplateFields.DEFINITIONS]
        entity = definitions[TemplateFields.ENTITIES][0]
        entity_id = entity[TemplateFields.ENTITY][TemplateFields.TEMPLATE_ID]
        relationship = definitions[TemplateFields.RELATIONSHIPS][0]
        relationship_dict = relationship[TemplateFields.RELATIONSHIP]
        relationship_dict[TemplateFields.TEMPLATE_ID] = entity_id

        self._test_execute_and_assert_with_fault_result(template, 2)

    def test_validate_relationship_with_invalid_target(self):

        template = self.clone_template
        definitions = template[TemplateFields.DEFINITIONS]
        relationship = definitions[TemplateFields.RELATIONSHIPS][0]
        relationship_dict = relationship[TemplateFields.RELATIONSHIP]
        relationship_dict[TemplateFields.TARGET] = 'unknown'

        self._test_execute_and_assert_with_fault_result(template, 3)

    def test_validate_relationship_with_invalid_source(self):

        template = self.clone_template
        definitions = template[TemplateFields.DEFINITIONS]
        relationship = definitions[TemplateFields.RELATIONSHIPS][0]
        relationship_dict = relationship[TemplateFields.RELATIONSHIP]
        relationship_dict[TemplateFields.SOURCE] = 'unknown'

        self._test_execute_and_assert_with_fault_result(template, 3)

    def test_validate_scenario_invalid_condition(self):

        template = self.clone_template
        scenario = template[TemplateFields.SCENARIOS][0]
        scenario_dict = scenario[TemplateFields.SCENARIO]

        scenario_dict[TemplateFields.CONDITION] = 'and resource'
        self._test_execute_and_assert_with_fault_result(template, 85)

        scenario_dict[TemplateFields.CONDITION] = 'resource or'
        self._test_execute_and_assert_with_fault_result(template, 85)

        scenario_dict[TemplateFields.CONDITION] = 'not or resource'
        self._test_execute_and_assert_with_fault_result(template, 85)

        scenario_dict[TemplateFields.CONDITION] = \
            'alarm_on_host (alarm or resource'
        self._test_execute_and_assert_with_fault_result(template, 85)

        scenario_dict[TemplateFields.CONDITION] = 'aaa'
        self._test_execute_and_assert_with_fault_result(template, 3)

        scenario_dict[TemplateFields.CONDITION] = 'resource and aaa'
        self._test_execute_and_assert_with_fault_result(template, 3)

    def test_validate_raise_alarm_action(self):
        # Test setup
        ids = ['123', '456', '789']
        action = self._create_raise_alarm_action('123')

        # Test action and assertions
        result = validator.validate_raise_alarm_action(action, ids)

        # Test Assertions
        self._test_assert_with_correct_result(result)

    def test_raise_alarm_action_validate_invalid_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_raise_alarm_action('unknown')

        # Test action
        result = validator.validate_raise_alarm_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 3)

    def test_validate_raise_alarm_action_without_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_raise_alarm_action('123')
        action[TemplateFields.ACTION_TARGET].pop(TemplateFields.TARGET)

        # Test action
        result = validator.validate_raise_alarm_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 127)

    def test_validate_raise_alarm_action_without_severity(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_raise_alarm_action('abc')
        action[TemplateFields.PROPERTIES].pop(TemplateFields.SEVERITY)

        # Test action
        result = validator.validate_raise_alarm_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 126)

    def test_validate_raise_alarm_action_without_alarm_name(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_raise_alarm_action('abc')
        action[TemplateFields.PROPERTIES].pop(TemplateFields.ALARM_NAME)

        # Test action
        result = validator.validate_raise_alarm_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 125)

    def test_validate_set_state_action(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_set_state_action('123')

        # Test action and assertions
        result = validator.validate_set_state_action(action, ids)

        # Test Assertions
        self._test_assert_with_correct_result(result)

    def test_validate_set_state_action_with_invalid_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_set_state_action('unknown')

        # Test action
        result = validator.validate_set_state_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 3)

    def test_validate_set_state_action_without_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_set_state_action('123')
        action[TemplateFields.ACTION_TARGET].pop(TemplateFields.TARGET)

        # Test action
        result = validator.validate_set_state_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 129)

    def test_validate_set_state_action_without_state_property(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_set_state_action('123')
        action[TemplateFields.PROPERTIES].pop(TemplateFields.STATE, None)

        # Test action
        result = validator.validate_set_state_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 128)

    def test_validate_mark_down_action(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_mark_down_action('123')

        # Test action and assertions
        result = validator.validate_mark_down_action(action, ids)

        # Test Assertions
        self._test_assert_with_correct_result(result)

    def test_validate_mark_down_action_with_invalid_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_mark_down_action('unknown')

        # Test action
        result = validator.validate_mark_down_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 3)

    def test_validate_mark_down_action_without_target_id(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_mark_down_action('123')
        action[TemplateFields.ACTION_TARGET].pop(TemplateFields.TARGET)

        # Test action
        result = validator.validate_mark_down_action(action, ids)

        # Test assertions
        self._test_assert_with_fault_result(result, 131)

    def test_validate_add_causal_relationship_action(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_add_causal_relationship_action('456', '123')

        # Test action and assertions
        result = validator.validate_add_causal_relationship_action(action, ids)

        # Test action and assertions
        self._test_assert_with_correct_result(result)

    def test_validate_add_causal_relationship_action_with_invalid_target(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_add_causal_relationship_action('unknown', '123')

        # Test action
        result = validator.validate_add_causal_relationship_action(action, ids)

        # Test assertion
        self._test_assert_with_fault_result(result, 3)

    def test_validate_add_causal_relationship_action_without_target(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_add_causal_relationship_action('456', '123')
        action[TemplateFields.ACTION_TARGET].pop(TemplateFields.TARGET, None)

        # Test action
        result = validator.validate_add_causal_relationship_action(action, ids)

        # Test assertion
        self._test_assert_with_fault_result(result, 130)

    def test_validate_add_causal_relationship_action_with_invalid_source(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_add_causal_relationship_action('456', 'unknown')

        # Test action
        result = validator.validate_add_causal_relationship_action(action, ids)

        # Test assertion
        self._test_assert_with_fault_result(result, 3)

    def test_validate_add_causal_relationship_action_without_source(self):

        # Test setup
        ids = ['123', '456', '789']
        action = self._create_add_causal_relationship_action('456', '123')
        action[TemplateFields.ACTION_TARGET].pop(TemplateFields.SOURCE, None)

        # Test action
        result = validator.validate_add_causal_relationship_action(action, ids)

        # Test assertion
        self._test_assert_with_fault_result(result, 130)

    def _test_execute_and_assert_with_fault_result(self,
                                                   template,
                                                   status_code):

        result = validator.content_validation(template)
        self._test_assert_with_fault_result(result, status_code)

    def _test_assert_with_fault_result(self, result, status_code):

        self.assertFalse(result.is_valid)
        self.assertTrue(result.comment.startswith(status_msgs[status_code]))
        self.assertEqual(result.status_code, status_code)

    def _test_execute_and_assert_with_correct_result(self, template):

        result = validator.content_validation(template)
        self._test_assert_with_correct_result(result)

    def _test_assert_with_correct_result(self, result):

        self.assertTrue(result.is_valid)
        self.assertEqual(result.comment, status_msgs[0])
        self.assertEqual(result.status_code, 0)

    def _create_scenario_actions(self, target, source):

        actions = []
        raise_alarm_action = self._create_raise_alarm_action(target)
        actions.append({TemplateFields.ACTION: raise_alarm_action})

        set_state_action = self._create_set_state_action(target)
        actions.append({TemplateFields.ACTION: set_state_action})

        mark_host_down_action = self._create_mark_down_action(target)
        actions.append({TemplateFields.ACTION: mark_host_down_action})

        causal_action = self._create_add_causal_relationship_action(target,
                                                                    source)
        actions.append({TemplateFields.ACTION: causal_action})

        return actions

    # Static methods:
    @staticmethod
    def _create_add_causal_relationship_action(target, source):

        action_target = {
            TemplateFields.TARGET: target,
            TemplateFields.SOURCE: source
        }
        action = {
            TemplateFields.ACTION_TYPE: ActionType.ADD_CAUSAL_RELATIONSHIP,
            TemplateFields.ACTION_TARGET: action_target}

        return action

    @staticmethod
    def _create_mark_down_action(target):

        action_target = {
            TemplateFields.TARGET: target
        }
        action = {
            TemplateFields.ACTION_TYPE: ActionType.MARK_DOWN,
            TemplateFields.ACTION_TARGET: action_target,
        }
        return action

    @staticmethod
    def _create_set_state_action(target):

        action_target = {
            TemplateFields.TARGET: target
        }
        properties = {
            TemplateFields.STATE: 'SUBOPTIMAL'
        }
        action = {
            TemplateFields.ACTION_TYPE: ActionType.SET_STATE,
            TemplateFields.ACTION_TARGET: action_target,
            TemplateFields.PROPERTIES: properties
        }
        return action

    @staticmethod
    def _create_raise_alarm_action(target):

        action_target = {
            TemplateFields.TARGET: target
        }
        properties = {
            TemplateFields.ALARM_NAME: 'VM_CPU_SUBOPTIMAL_PERFORMANCE',
            TemplateFields.SEVERITY: 'critical'
        }
        action = {
            TemplateFields.ACTION_TYPE: ActionType.RAISE_ALARM,
            TemplateFields.ACTION_TARGET: action_target,
            TemplateFields.PROPERTIES: properties
        }
        return action

    @staticmethod
    def _hide_useless_logging_messages():

        validator_path = 'vitrage.evaluator.template_validation.' \
                         'template_content_validator'
        content_validator_log = logging.getLogger(validator_path)
        content_validator_log.setLevel(logging.FATAL)
