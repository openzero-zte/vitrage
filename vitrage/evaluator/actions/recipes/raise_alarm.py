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

from vitrage.evaluator.actions.recipes.action_steps import ADD_VERTEX
from vitrage.evaluator.actions.recipes.action_steps import NOTIFY
from vitrage.evaluator.actions.recipes.action_steps import REMOVE_VERTEX
from vitrage.evaluator.actions.recipes import base
from vitrage.evaluator.actions.recipes.base import ActionStepWrapper
from vitrage.evaluator.template_fields import TemplateFields as TFields


class RaiseAlarm(base.Recipe):

    @staticmethod
    def get_do_recipe(action_spec):

        add_vertex_params = {
            TFields.TARGET: action_spec.targets[TFields.TARGET],
            TFields.ALARM_NAME: action_spec.properties[TFields.ALARM_NAME]
        }
        add_vertex_step = ActionStepWrapper(ADD_VERTEX, add_vertex_params)

        notify_step = RaiseAlarm._get_notify_step()

        return [add_vertex_step, notify_step]

    @staticmethod
    def get_undo_recipe(action_spec):

        remove_vertex_params = {
            TFields.TARGET: action_spec.targets[TFields.TARGET],
            TFields.ALARM_NAME: action_spec.properties[TFields.ALARM_NAME]
        }
        remove_vertex_step = ActionStepWrapper(REMOVE_VERTEX,
                                               remove_vertex_params)
        notify_step = RaiseAlarm._get_notify_step()

        return [remove_vertex_step, notify_step]

    @staticmethod
    def _get_notify_step():

        # TODO(lhartal): add params
        return ActionStepWrapper(NOTIFY, {})
