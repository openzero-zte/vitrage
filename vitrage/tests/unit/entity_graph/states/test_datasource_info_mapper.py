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

from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.nagios import NAGIOS_DATASOURCE
from vitrage.datasources.nova.host import NOVA_HOST_DATASOURCE
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources.nova.zone import NOVA_ZONE_DATASOURCE
from vitrage.entity_graph.mappings.datasource_info_mapper import \
    DatasourceInfoMapper
from vitrage.entity_graph.mappings.operational_resource_state import \
    OperationalResourceState
from vitrage.graph.utils import create_vertex
from vitrage.opts import register_opts
from vitrage.tests import base
from vitrage.tests.mocks import utils


class TestDatasourceInfoMapper(base.BaseTest):

    ENTITY_GRAPH_OPTS = [
        cfg.StrOpt('datasources_values_dir',
                   default=utils.get_resources_dir() + '/datasources_values'),
    ]

    DATASOURCES_OPTS = [
        cfg.ListOpt('types',
                    default=[NAGIOS_DATASOURCE,
                             NOVA_HOST_DATASOURCE,
                             NOVA_INSTANCE_DATASOURCE,
                             NOVA_ZONE_DATASOURCE],
                    help='Names of supported data sources'),

        cfg.ListOpt('path',
                    default=['vitrage.datasources'],
                    help='base path for datasources')
    ]

    @staticmethod
    def _load_datasources(conf):
        for datasource_name in conf.datasources.types:
            register_opts(conf, datasource_name, conf.datasources.path)

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        super(TestDatasourceInfoMapper, cls).setUpClass()
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.ENTITY_GRAPH_OPTS, group='entity_graph')
        cls.conf.register_opts(cls.DATASOURCES_OPTS, group='datasources')
        cls._load_datasources(cls.conf)

    def test_load_datasource_state_without_errors(self):
        # action
        state_manager = DatasourceInfoMapper(self.conf)

        # test assertions

        # Total datasources plus the evaluator which is not definable
        total_datasources = len(self.conf.datasources.types) + 1
        self.assertEqual(total_datasources,
                         len(state_manager.datasources_state_confs))

    def test_load_datasources_state_with_errors(self):
        # setup
        entity_graph_opts = [
            cfg.StrOpt('datasources_values_dir',
                       default=utils.get_resources_dir() +
                       '/datasources_values/erroneous_values'),
        ]
        conf = cfg.ConfigOpts()
        conf.register_opts(entity_graph_opts, group='entity_graph')
        conf.register_opts(self.DATASOURCES_OPTS, group='datasources')
        self._load_datasources(conf)

        # action
        state_manager = DatasourceInfoMapper(conf)

        # test assertions
        missing_states = 1
        erroneous_values = 1
        num_valid_datasources = len(state_manager.datasources_state_confs) + \
            missing_states + erroneous_values
        self.assertEqual(num_valid_datasources, len(conf.datasources.types))

    def test_operational_state_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        operational_state = \
            state_manager.operational_state(NOVA_INSTANCE_DATASOURCE,
                                            'BUILDING')

        # test assertions
        self.assertEqual(OperationalResourceState.TRANSIENT, operational_state)

    def test_operational_state_not_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        operational_state = \
            state_manager.operational_state(NOVA_INSTANCE_DATASOURCE,
                                            'NON EXISTING STATE')

        # test assertions
        self.assertEqual(OperationalResourceState.NA, operational_state)

    def test_operational_state_datasource_not_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        operational_state = \
            state_manager.operational_state('NON EXISTING DATASOURCE',
                                            'BUILDING')

        # test assertions
        self.assertEqual(DatasourceInfoMapper.UNDEFINED_DATASOURCE,
                         operational_state)

    def test_state_priority(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        state_priority = \
            state_manager.state_priority(NOVA_INSTANCE_DATASOURCE,
                                         'ACTIVE')

        # test assertions
        self.assertEqual(10, state_priority)

    def test_state_priority_not_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        state_priority = \
            state_manager.state_priority(NOVA_INSTANCE_DATASOURCE,
                                         'NON EXISTING STATE')

        # test assertions
        self.assertEqual(0, state_priority)

    def test_state_priority_datasource_not_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)

        # action
        state_priority = \
            state_manager.state_priority('NON EXISTING DATASOURCE',
                                         'ACTIVE')

        # test assertions
        self.assertEqual(DatasourceInfoMapper.UNDEFINED_DATASOURCE,
                         state_priority)

    def test_aggregated_state(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)
        metadata1 = {VProps.VITRAGE_STATE: 'SUSPENDED'}
        new_vertex1 = create_vertex('12345',
                                    entity_state='ACTIVE',
                                    entity_category=EntityCategory.RESOURCE,
                                    entity_type=NOVA_INSTANCE_DATASOURCE,
                                    metadata=metadata1)
        metadata2 = {VProps.VITRAGE_STATE: 'ACTIVE'}
        new_vertex2 = create_vertex('23456',
                                    entity_state='SUSPENDED',
                                    entity_category=EntityCategory.RESOURCE,
                                    entity_type=NOVA_INSTANCE_DATASOURCE,
                                    metadata=metadata2)

        # action
        state_manager.aggregated_state(new_vertex1, None)
        state_manager.aggregated_state(new_vertex2, None)

        # test assertions
        self.assertEqual('SUSPENDED', new_vertex1[VProps.AGGREGATED_STATE])
        self.assertEqual(OperationalResourceState.SUBOPTIMAL,
                         new_vertex1[VProps.OPERATIONAL_STATE])
        self.assertEqual('SUSPENDED', new_vertex2[VProps.AGGREGATED_STATE])
        self.assertEqual(OperationalResourceState.SUBOPTIMAL,
                         new_vertex2[VProps.OPERATIONAL_STATE])

    def test_aggregated_state_functionalities(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)
        new_vertex1 = create_vertex('12345',
                                    entity_state='ACTIVE',
                                    entity_category=EntityCategory.RESOURCE,
                                    entity_type=NOVA_INSTANCE_DATASOURCE)
        metadata2 = {VProps.VITRAGE_STATE: 'SUBOPTIMAL'}
        new_vertex2 = create_vertex('23456',
                                    entity_category=EntityCategory.RESOURCE,
                                    entity_type=NOVA_INSTANCE_DATASOURCE,
                                    metadata=metadata2)
        metadata3 = {VProps.VITRAGE_STATE: 'SUBOPTIMAL'}
        new_vertex3 = create_vertex('34567',
                                    entity_state='ACTIVE',
                                    entity_category=EntityCategory.RESOURCE,
                                    entity_type=NOVA_INSTANCE_DATASOURCE)
        graph_vertex3 = create_vertex('34567',
                                      entity_state='SUSPENDED',
                                      entity_category=EntityCategory.RESOURCE,
                                      entity_type=NOVA_INSTANCE_DATASOURCE,
                                      metadata=metadata3)

        # action
        state_manager.aggregated_state(new_vertex1,
                                       None)
        state_manager.aggregated_state(new_vertex2,
                                       None)
        state_manager.aggregated_state(new_vertex3,
                                       graph_vertex3)

        # test assertions
        self.assertEqual('ACTIVE', new_vertex1[VProps.AGGREGATED_STATE])
        self.assertEqual(OperationalResourceState.OK,
                         new_vertex1[VProps.OPERATIONAL_STATE])
        self.assertEqual('SUBOPTIMAL', new_vertex2[VProps.AGGREGATED_STATE])
        self.assertEqual(OperationalResourceState.SUBOPTIMAL,
                         new_vertex2[VProps.OPERATIONAL_STATE])
        self.assertEqual('SUBOPTIMAL', new_vertex3[VProps.AGGREGATED_STATE])
        self.assertEqual(OperationalResourceState.SUBOPTIMAL,
                         new_vertex3[VProps.OPERATIONAL_STATE])

    def test_aggregated_state_datasource_not_exists(self):
        # setup
        state_manager = DatasourceInfoMapper(self.conf)
        metadata = {VProps.VITRAGE_STATE: 'SUSPENDED'}
        new_vertex = create_vertex('12345',
                                   entity_state='ACTIVE',
                                   entity_category=EntityCategory.RESOURCE,
                                   entity_type='NON EXISTING DATASOURCE',
                                   metadata=metadata)

        # action
        state_manager.aggregated_state(new_vertex, None)

        # test assertions
        self.assertEqual(DatasourceInfoMapper.UNDEFINED_DATASOURCE,
                         new_vertex[VProps.AGGREGATED_STATE])
        self.assertEqual(DatasourceInfoMapper.UNDEFINED_DATASOURCE,
                         new_vertex[VProps.OPERATIONAL_STATE])
