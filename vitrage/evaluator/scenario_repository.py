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
from collections import defaultdict
from collections import namedtuple
import uuid

from oslo_log import log

from vitrage.common import datetime_utils
from vitrage.common import file_utils
from vitrage.evaluator.base import Template
from vitrage.evaluator.template_data import RELATIONSHIP
from vitrage.evaluator.template_data import TemplateData
from vitrage.evaluator.template_validation.template_content_validator import \
    content_validation
from vitrage.evaluator.template_validation.template_syntax_validator import \
    syntax_validation

LOG = log.getLogger(__name__)

EdgeKeyScenario = namedtuple('EdgeKeyScenario', ['label', 'source', 'target'])


class ScenarioRepository(object):
    def __init__(self, conf):
        self._templates = {}
        self.relationship_scenarios = defaultdict(list)
        self.entity_scenarios = defaultdict(list)
        self._load_templates_files(conf)

    @property
    def templates(self):
        return self._templates

    @templates.setter
    def templates(self, templates):
        self._templates = templates

    def get_scenarios_by_vertex(self, vertex):

        entity_key = frozenset(vertex.properties.items())

        scenarios = []
        for scenario_key, value in self.entity_scenarios.items():
            if scenario_key.issubset(entity_key):
                scenarios += value
        return scenarios

    def get_scenarios_by_edge(self, edge_description):

        key = self._create_edge_scenario_key(edge_description)
        scenarios = []

        for scenario_key, value in self.relationship_scenarios.items():

            check_label = key.label == scenario_key.label
            check_source_issubset = scenario_key.source.issubset(key.source)
            check_target_issubset = scenario_key.target.issubset(key.target)

            if check_label and check_source_issubset and check_target_issubset:
                scenarios += value

        return scenarios

    def add_template(self, template_def):

        current_time = datetime_utils.utcnow()

        result = syntax_validation(template_def)
        if not result.is_valid:
            LOG.info('Unable to load template: %s' % result.comment)
        else:
            result = content_validation(template_def)
            if not result.is_valid:
                LOG.info('Unable to load template: %s' % result.comment)

        template_uuid = uuid.uuid4()
        self.templates[str(template_uuid)] = Template(template_uuid,
                                                      template_def,
                                                      current_time,
                                                      result)
        if result.is_valid:
            template_data = TemplateData(template_def)
            self._add_template_scenarios(template_data)

    def _load_templates_files(self, conf):

        templates_dir = conf.evaluator.templates_dir
        template_defs = file_utils.load_yaml_files(templates_dir)

        for template_def in template_defs:
            self.add_template(template_def)

    def _add_template_scenarios(self, template):
        for scenario in template.scenarios:
            self._handle_condition(scenario)

    def _handle_condition(self, scenario):
        for clause in scenario.condition:
            self._handle_clause(clause, scenario)

    def _handle_clause(self, clause, scenario):
        for condition_var in clause:
            if condition_var.type == RELATIONSHIP:
                edge_desc = condition_var.variable
                self._add_relationship(scenario, edge_desc)
                self._add_entity(scenario, edge_desc.source)
                self._add_entity(scenario, edge_desc.target)
            else:  # Entity
                self._add_entity(scenario, condition_var.variable)

    @staticmethod
    def _create_scenario_key(properties):
        return frozenset(properties)

    def _add_relationship(self, scenario, edge_desc):

        key = self._create_edge_scenario_key(edge_desc)
        scenarios = self.relationship_scenarios[key]

        if not self.contains(scenarios, scenario):
            self.relationship_scenarios[key].append((edge_desc, scenario))

    @staticmethod
    def _create_edge_scenario_key(edge_desc):

        return EdgeKeyScenario(edge_desc.edge.label,
                               frozenset(edge_desc.source.properties.items()),
                               frozenset(edge_desc.target.properties.items()))

    def _add_entity(self, scenario, entity):

        key = frozenset(list(entity.properties.items()))
        scenarios = self.entity_scenarios[key]

        if not self.contains(scenarios, scenario):
            self.entity_scenarios[key].append((entity, scenario))

    @staticmethod
    def contains(scenarios, scenario):
        return any(s[1].id == scenario.id for s in scenarios)
