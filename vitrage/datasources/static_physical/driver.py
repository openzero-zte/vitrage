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
# WARRANTIES OR  CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import os

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EventAction
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common import file_utils
from vitrage.datasources.driver_base import DriverBase
from vitrage.datasources.static_physical import STATIC_PHYSICAL_DATASOURCE


class StaticPhysicalDriver(DriverBase):
    @staticmethod
    def get_event_types(conf):
        return []

    @staticmethod
    def enrich_event(event, event_type):
        pass

    ENTITIES_SECTION = 'entities'

    def __init__(self, conf):
        super(StaticPhysicalDriver, self).__init__()
        self.cfg = conf
        self.cache = {}

    def get_all(self, sync_mode):
        return self.make_pickleable(self._get_all_entities(),
                                    STATIC_PHYSICAL_DATASOURCE,
                                    sync_mode)

    def get_changes(self, sync_mode):
        return self.make_pickleable(self._get_changes_entities(),
                                    STATIC_PHYSICAL_DATASOURCE,
                                    sync_mode)

    def _get_all_entities(self):
        static_entities = []

        if os.path.isdir(self.cfg.static_physical.directory):
            files = file_utils.load_files(
                self.cfg.static_physical.directory, '.yaml')

            for file_ in files:
                full_path = self.cfg.static_physical.directory \
                    + '/' + file_
                static_entities += self._get_entities_from_file(file_,
                                                                full_path)

        return static_entities

    def _get_entities_from_file(self, file_, path):
        static_entities = []
        config = file_utils.load_yaml_file(path)

        for entity in config[self.ENTITIES_SECTION]:
            static_entities.append(entity.copy())

        self.cache[file_] = config

        return static_entities

    def _get_changes_entities(self):

        entities_updates = []
        files = file_utils.load_files(
            self.cfg.static_physical.directory, '.yaml')

        for file_ in files:
            full_path = self.cfg.static_physical.directory +\
                '/' + file_
            config = file_utils.load_yaml_file(full_path)
            if config:
                if file_ in self.cache:
                    if str(config) != str(self.cache[file_]):
                        # TODO(alexey_weyl): need also to remove deleted
                        #                   files from cache
                        old_config = copy.deepcopy(config)

                        self._update_on_existing_entities(
                            self.cache[file_][self.ENTITIES_SECTION],
                            config[self.ENTITIES_SECTION],
                            entities_updates)

                        self._update_on_new_entities(
                            config[self.ENTITIES_SECTION],
                            self.cache[file_][self.ENTITIES_SECTION],
                            entities_updates)

                        self.cache[file_] = old_config
                else:
                    self.cache[file_] = config
                    entities_updates += \
                        self._get_entities_from_file(file_, full_path)

        # iterate over deleted files
        deleted_files = set(self.cache.keys()) - set(files)
        for file_ in deleted_files:
            self._update_on_existing_entities(
                self.cache[file_][self.ENTITIES_SECTION],
                {},
                entities_updates)
            del self.cache[file_]

        return entities_updates

    def _update_on_existing_entities(self,
                                     old_entities,
                                     new_entities,
                                     updates):
        for old_entity in old_entities:
            if not new_entities or old_entity not in new_entities:
                new_entity = self._find_entity(old_entity, new_entities)
                if not new_entity:
                    self._set_event_type(old_entity, EventAction.DELETE_ENTITY)
                    updates.append(old_entity.copy())
                else:
                    self._set_event_type(new_entity, EventAction.UPDATE_ENTITY)
                    updates.append(new_entity.copy())

    @staticmethod
    def _find_entity(new_entity, entities):
        for entity in entities:
            if entity[VProps.TYPE] == new_entity[VProps.TYPE] \
                    and entity[VProps.ID] == new_entity[VProps.ID]:
                return entity
        return None

    @staticmethod
    def _update_on_new_entities(new_entities, old_entities, updates):
        for entity in new_entities:
            if entity not in updates and entity not in old_entities:
                updates.append(entity.copy())

    @staticmethod
    def _set_event_type(entity, event_type):
        entity[DSProps.EVENT_TYPE] = event_type
