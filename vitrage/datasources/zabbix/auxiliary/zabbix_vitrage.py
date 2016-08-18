#!/usr/bin/env python

# coding: utf-8

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

import argparse
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from oslo_config import cfg
import oslo_messaging as messaging
import six
import socket
import sys
import uuid

'''
Expected input:
Send To:
Vitrage Message Bus address e.g.
rabbit://userrabbit:passrabbit@127.0.0.1:5672/
Subject: {TRIGGER.STATUS}
Message:
    host={HOST.NAME1}
    hostid={HOST.ID1}
    hostip={HOST.IP1}
    triggerid={TRIGGER.ID}
    description={TRIGGER.NAME}
    rawtext={TRIGGER.NAME.ORIG}
    expression={TRIGGER.EXPRESSION}
    value={TRIGGER.VALUE}
    priority={TRIGGER.NSEVERITY}
    lastchange={EVENT.DATE} {EVENT.TIME}
'''


LOG_FILE = '/var/log/zabbix/zabbix_vitrage.log'
LOG_MAX_SIZE = 10240
LOG_FORMAT = '%(asctime)s.%(msecs).03d %(name)s[%(process)d] %(threadName)s %' \
             '(levelname)s - %(message)s'
LOG_DATE_FMT = '%Y.%m.%d %H:%M:%S'
ZABBIX_EVENT_TYPE = 'zabbix.alarm'

debug = False


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('sendto', help='Vitrage message bus path')
    parser.add_argument('topic', help='zabbix topic')
    parser.add_argument('body', help='zabbix body')
    args = parser.parse_args()

    logging.debug('[vitrage] sendto=%s, topic=%s, body=%s',
                  args.sendto, args.topic, args.body)

    transport_url = args.sendto
    transport = messaging.get_transport(cfg.CONF, transport_url)
    driver = 'messagingv2'
    publisher = 'zabbix_%s' % socket.gethostname()
    notifier = messaging.Notifier(transport,
                                  driver=driver,
                                  publisher_id=publisher,
                                  topic='vitrage_notifications')

    alarm_status = args.topic.lower()
    event_type = '%s.%s' % (ZABBIX_EVENT_TYPE, alarm_status)

    payload = {key.lower().strip(): prop.strip() for key, prop in
               (line.split('=') for line in args.body.splitlines())}

    logging.debug('[vitrage] publisher: %s, event: %s, payload %s',
                  publisher, event_type, payload)

    notifier.info(ctxt={'message_id': six.text_type(uuid.uuid4()),
                        'publisher_id': publisher,
                        'timestamp': datetime.utcnow()},
                  event_type=event_type,
                  payload=payload)

if __name__ == '__main__':

    if debug:
        logging.basicConfig(stream=sys.stderr, format=LOG_FORMAT,
                            datefmt=LOG_DATE_FMT, level=logging.DEBUG)
    else:
        logging.basicConfig(filename=LOG_FILE, format=LOG_FORMAT,
                            datefmt=LOG_DATE_FMT, level=logging.DEBUG)
    log = logging.getLogger()
    handler = RotatingFileHandler(filename=LOG_FILE,
                                  maxBytes=LOG_MAX_SIZE,
                                  backupCount=1)
    log.addHandler(handler)
    main()
