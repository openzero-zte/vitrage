# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,  software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND,  either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from nova_plugins.novaclient_plugin import NovaClientPlugin


class NovaHostPlugin(NovaClientPlugin):

    def __init__(self, version, user, password, project, auth_url):
        super(NovaHostPlugin, self).__init__(version,
                                             user,
                                             password,
                                             project,
                                             auth_url)

    def filter_none_compute_hosts(self, entities):
        compute_hosts = []
        for host in entities:
            host_dict = host.__dict__
            if host_dict['service'] and host_dict['service'] == 'compute':
                compute_hosts.append(host)
        return compute_hosts

    def get_all(self):
        return self.make_picklable(self.filter_none_compute_hosts(
            self.client.hosts.list()), 'nova.host', ['manager'])
