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

from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources import transformer_base as tbase
import vitrage.graph.utils as graph_utils


LOG = logging.getLogger(__name__)


class ResourceTransformerBase(tbase.TransformerBase):

    def __init__(self, transformers, conf):
        super(ResourceTransformerBase, self).__init__(transformers, conf)

    def _key_values(self, *args):
        return (EntityCategory.RESOURCE,) + args

    def create_placeholder_vertex(self, **kwargs):
        if VProps.TYPE not in kwargs:
            LOG.error("Can't create placeholder vertex. Missing property TYPE")
            raise ValueError('Missing property TYPE')

        if VProps.ID not in kwargs:
            LOG.error("Can't create placeholder vertex. Missing property ID")
            raise ValueError('Missing property ID')

        key_fields = self._key_values(kwargs[VProps.TYPE], kwargs[VProps.ID])

        return graph_utils.create_vertex(
            tbase.build_key(key_fields),
            entity_id=kwargs[VProps.ID],
            entity_category=EntityCategory.RESOURCE,
            entity_type=kwargs[VProps.TYPE],
            sample_timestamp=kwargs[VProps.SAMPLE_TIMESTAMP],
            is_placeholder=True)
