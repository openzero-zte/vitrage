# Copyright 2016 - Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,  software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND,  either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from collections import defaultdict

from oslo_log import log
import oslo_messaging
from oslo_service import service as os_service

from vitrage.common.constants import UpdateMethod
from vitrage import messaging


LOG = log.getLogger(__name__)


class ListenerService(os_service.Service):

    def __init__(self, conf, drivers, callback):
        super(ListenerService, self).__init__()

        self.enrich_callbacks_by_events = \
            self._create_callbacks_by_events_dict(drivers, conf)

        topic = conf.datasources.notification_topic
        self.listener = self._get_topic_listener(conf, topic, callback)

    def start(self):
        LOG.info("Vitrage data source Listener Service - Starting...")

        super(ListenerService, self).start()
        self.listener.start()

        LOG.info("Vitrage data source Listener Service - Started!")

    def stop(self, graceful=False):
        LOG.info("Vitrage data source Listener Service - Stopping...")

        super(ListenerService, self).stop(graceful)

        LOG.info("Vitrage data source Listener Service - Stopped!")

    @classmethod
    def _create_callbacks_by_events_dict(cls, drivers, conf):
        ret = defaultdict(list)
        push_drivers = cls._get_push_drivers(drivers, conf)

        for driver in push_drivers:
            for event in driver.get_event_types(conf):
                ret[event].append(driver.enrich_event)

        return ret

    @staticmethod
    def _get_push_drivers(drivers, conf):
        return (driver_cls for datasource, driver_cls in drivers.items()
                if conf[datasource].update_method.lower() == UpdateMethod.PUSH)

    def _get_topic_listener(self, conf, topic, callback):
        # Create a listener for each topic
        transport = messaging.get_transport(conf)
        targets = [oslo_messaging.Target(topic=topic, exchange='nova')]

        return messaging.get_notification_listener(
            transport,
            targets,
            [NotificationsEndpoint(self.enrich_callbacks_by_events, callback)])


class NotificationsEndpoint(object):

    def __init__(self, enrich_callback_by_events, enqueue_callback):
        self.enrich_callbacks_by_events = enrich_callback_by_events
        self.enqueue_callback = enqueue_callback

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        for event_string in self.enrich_callbacks_by_events:
            if str(event_type) == event_string:

                callbacks = self.enrich_callbacks_by_events[event_string]
                enriched_events = [callback(payload, event_type)
                                   for callback in callbacks]
                self._enqueue_events(enriched_events)

    def _enqueue_events(self, enriched_events):
        for event in enriched_events:
            self.enqueue_callback(event)
            LOG.debug('EVENT ENQUEUED: \n' + str(event))
