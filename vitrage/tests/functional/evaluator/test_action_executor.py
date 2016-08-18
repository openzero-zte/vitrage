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


from oslo_config import cfg
from oslo_log import log as logging

from six.moves import queue
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.alarm_properties import AlarmProperties as AlarmProps
from vitrage.datasources.nagios import NAGIOS_DATASOURCE
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.entity_graph.mappings.operational_resource_state import \
    OperationalResourceState
from vitrage.evaluator.actions.action_executor import ActionExecutor
from vitrage.evaluator.actions.base import ActionMode
from vitrage.evaluator.actions.base import ActionType
from vitrage.evaluator.actions.evaluator_event_transformer import VITRAGE_TYPE
from vitrage.evaluator.template_data import ActionSpecs
from vitrage.evaluator.template_fields import TemplateFields as TFields
from vitrage.opts import register_opts
from vitrage.tests.functional.base import TestFunctionalBase

LOG = logging.getLogger(__name__)


class TestActionExecutor(TestFunctionalBase):

    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls):
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.PROCESSOR_OPTS, group='entity_graph')
        cls.conf.register_opts(cls.DATASOURCES_OPTS, group='datasources')

        for datasource_name in cls.conf.datasources.types:
            register_opts(cls.conf, datasource_name, cls.conf.datasources.path)

    def test_execute_update_vertex(self):

        # Test Setup
        processor = self._create_processor_with_graph(self.conf)

        vertex_attrs = {VProps.TYPE: NOVA_HOST_DATASOURCE}
        host_vertices = processor.entity_graph.get_vertices(
            vertex_attr_filter=vertex_attrs)
        host_vertex_before = host_vertices[0]

        targets = {TFields.TARGET: host_vertex_before}
        props = {TFields.STATE: OperationalResourceState.SUBOPTIMAL}
        action_spec = ActionSpecs(ActionType.SET_STATE, targets, props)

        event_queue = queue.Queue()
        action_executor = ActionExecutor(event_queue)

        # Test Action - do
        action_executor.execute(action_spec, ActionMode.DO)
        processor.process_event(event_queue.get())

        host_vertex_after = processor.entity_graph.get_vertex(
            host_vertex_before.vertex_id)

        # Test Assertions
        agg_state_before = host_vertex_before.get(VProps.AGGREGATED_STATE)
        self.assertTrue(agg_state_before !=
                        OperationalResourceState.SUBOPTIMAL)
        self.assertFalse(VProps.VITRAGE_STATE in host_vertex_before.properties)

        agg_state_after = host_vertex_after.get(VProps.AGGREGATED_STATE)
        self.assertEqual(agg_state_after, OperationalResourceState.SUBOPTIMAL)
        v_state_after = host_vertex_after.get(VProps.VITRAGE_STATE)
        self.assertEqual(v_state_after, OperationalResourceState.SUBOPTIMAL)

        # Test Action - undo
        action_executor.execute(action_spec, ActionMode.UNDO)
        processor.process_event(event_queue.get())

        host_vertex_after_undo = processor.entity_graph.get_vertex(
            host_vertex_before.vertex_id)

        # Test Assertions
        agg_state_after_undo = host_vertex_before.get(VProps.AGGREGATED_STATE)
        self.assertEqual(agg_state_after_undo, agg_state_before)
        self.assertTrue(
            VProps.VITRAGE_STATE not in host_vertex_after_undo.properties)

    def test_execute_add_edge(self):

        # Test Setup
        processor = self._create_processor_with_graph(self.conf)

        vertex_attrs = {VProps.TYPE: NOVA_HOST_DATASOURCE}
        host_vertices = processor.entity_graph.get_vertices(
            vertex_attr_filter=vertex_attrs)

        host_1 = host_vertices[0]
        nagios_event1 = TestActionExecutor._get_nagios_event(
            host_1.get(VProps.ID), NOVA_HOST_DATASOURCE)
        processor.process_event(nagios_event1)

        host_2 = host_vertices[1]
        nagios_event2 = TestActionExecutor._get_nagios_event(
            host_2.get(VProps.ID), NOVA_HOST_DATASOURCE)
        processor.process_event(nagios_event2)

        alarms_attrs = {VProps.TYPE: NAGIOS_DATASOURCE}
        alarms_vertices = processor.entity_graph.get_vertices(
            vertex_attr_filter=alarms_attrs)

        alarm1 = alarms_vertices[0]
        alarm2 = alarms_vertices[1]
        targets = {
            TFields.TARGET: alarm1,
            TFields.SOURCE: alarm2
        }
        action_spec = ActionSpecs(ActionType.ADD_CAUSAL_RELATIONSHIP,
                                  targets,
                                  {})

        event_queue = queue.Queue()
        action_executor = ActionExecutor(event_queue)

        before_edge = processor.entity_graph.get_edge(alarm2.vertex_id,
                                                      alarm1.vertex_id,
                                                      EdgeLabel.CAUSES)
        # Test Action - do
        action_executor.execute(action_spec, ActionMode.DO)
        processor.process_event(event_queue.get())

        new_edge = processor.entity_graph.get_edge(alarm2.vertex_id,
                                                   alarm1.vertex_id,
                                                   EdgeLabel.CAUSES)
        # Test Assertions
        self.assertIsNone(before_edge)
        self.assertIsNotNone(new_edge)

    def test_execute_add_vertex(self):

        # Test Setup
        processor = self._create_processor_with_graph(self.conf)

        vertex_attrs = {VProps.TYPE: NOVA_HOST_DATASOURCE}
        host_vertices = processor.entity_graph.get_vertices(
            vertex_attr_filter=vertex_attrs)

        host = host_vertices[0]

        targets = {TFields.TARGET: host}
        props = {
            TFields.ALARM_NAME: 'VM_CPU_SUBOPTIMAL_PERFORMANCE',
            TFields.SEVERITY: 'CRITICAL',
            VProps.STATE: AlarmProps.ACTIVE_STATE
        }

        # Raise alarm action adds new vertex with type vitrage to the graph
        action_spec = ActionSpecs(ActionType.RAISE_ALARM, targets, props)

        alarm_vertex_attrs = {VProps.TYPE: VITRAGE_TYPE}
        before_alarms = processor.entity_graph.get_vertices(
            vertex_attr_filter=alarm_vertex_attrs)
        event_queue = queue.Queue()
        action_executor = ActionExecutor(event_queue)

        expected_alarm_id = 'ALARM:vitrage:%s:%s' % (props[TFields.ALARM_NAME],
                                                     host.vertex_id)
        # Test Action
        action_executor.execute(action_spec, ActionMode.DO)
        processor.process_event(event_queue.get())

        after_alarms = processor.entity_graph.get_vertices(
            vertex_attr_filter=alarm_vertex_attrs)

        # Assertions
        self.assertEqual(len(before_alarms) + 1, len(after_alarms))
        self.assert_is_not_empty(after_alarms)

        alarms = [alarm for alarm in after_alarms
                  if alarm.vertex_id == expected_alarm_id]

        # Expected exactly one alarm with expected  id
        self.assertEqual(1, len(alarms))
        alarm = alarms[0]

        self.assertEqual(alarm.properties[VProps.CATEGORY],
                         EntityCategory.ALARM)
        self.assertEqual(alarm.properties[VProps.TYPE],
                         VITRAGE_TYPE)
        self.assertEqual(alarm.properties[VProps.SEVERITY],
                         props[TFields.SEVERITY])
        self.assertEqual(alarm.properties[VProps.OPERATIONAL_SEVERITY],
                         props[TFields.SEVERITY])
        self.assertEqual(alarm.properties[VProps.STATE],
                         AlarmProps.ACTIVE_STATE)

    def test_execute_add_and_remove_vertex(self):

        # Test Setup
        processor = self._create_processor_with_graph(self.conf)

        vertex_attrs = {VProps.TYPE: NOVA_HOST_DATASOURCE}
        host_vertices = processor.entity_graph.get_vertices(
            vertex_attr_filter=vertex_attrs)

        host = host_vertices[0]

        targets = {TFields.TARGET: host}
        props = {
            TFields.ALARM_NAME: 'VM_CPU_SUBOPTIMAL_PERFORMANCE',
            TFields.SEVERITY: 'CRITICAL',
            VProps.STATE: AlarmProps.ACTIVE_STATE
        }
        action_spec = ActionSpecs(ActionType.RAISE_ALARM, targets, props)

        add_vertex_event = TestActionExecutor._get_vitrage_add_vertex_event(
            host,
            props[TFields.ALARM_NAME],
            props[TFields.SEVERITY])

        processor.process_event(add_vertex_event)

        alarm_vertex_attrs = {VProps.TYPE: VITRAGE_TYPE,
                              VProps.IS_DELETED: False}
        before_alarms = processor.entity_graph.get_vertices(
            vertex_attr_filter=alarm_vertex_attrs)

        event_queue = queue.Queue()
        action_executor = ActionExecutor(event_queue)

        # Test Action - undo
        action_executor.execute(action_spec, ActionMode.UNDO)
        event = event_queue.get()
        processor.process_event(event)

        after_alarms = processor.entity_graph.get_vertices(
            vertex_attr_filter=alarm_vertex_attrs)

        # Test Assertions
        self.assertEqual(len(before_alarms) - 1, len(after_alarms))

    @staticmethod
    def _get_nagios_event(resource_name, resource_type):

        return {'last_check': '2016-02-07 15:26:04',
                'resource_name': resource_name,
                'resource_type': resource_type,
                'service': 'Check_MK',
                'status': 'CRITICAL',
                'status_info': 'test test test',
                'sync_mode': 'snapshot',
                'sync_type': 'nagios',
                'sample_date': '2016-02-07 15:26:04'}

    @staticmethod
    def _get_vitrage_add_vertex_event(target_vertex, alarm_name, severity):

        return {'target': target_vertex.vertex_id,
                'update_timestamp': '2016-03-17 11:33:32.443002',
                'sync_mode': 'update',
                'alarm_name': alarm_name,
                'state': 'Active',
                'type': 'add_vertex',
                'sync_type': 'vitrage',
                'severity': 'CRITICAL',
                'sample_timestamp': '2016-03-17 11:33:32.443002+00:00'}
