#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import collections

import mock
import pytest

from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtVolume(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtVolume, self).setUp()

        self.sleep_mock = self.patch('time.sleep')

        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.driver.libvirt.libvirt_driver.open',
                   self.open_mock, create=True)

        self.os_mock = self.patch('devops.helpers.helpers.os')
        # noinspection PyPep8Naming
        Size = collections.namedtuple('Size', ['st_size'])
        self.file_sizes = {
            '/tmp/admin.iso': Size(st_size=5 * 1024 ** 3),
            '/tmp/admin2.iso': Size(st_size=6442000000),
        }
        self.os_mock.stat.side_effect = self.file_sizes.get

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default',
            storage_pool_name='default-pool')

        self.node = self.group.add_node(
            name='test_node',
            role='default',
            architecture='i686',
            hypervisor='test',
        )

        self.d = self.group.driver

    @pytest.mark.xfail(reason="need libvirtd >= 1.2.12")
    def test_define_erase(self):
        volume = self.node.add_volume(
            name='test_volume',
            capacity=512,
        )

        volume.define()

        assert volume.capacity == 512
        assert volume.get_capacity() == 549755813888
        assert volume.get_path() == (
            '/default-pool/test_env_test_node_test_volume')
        assert volume.get_allocation() == 549755813888

        xml = volume._libvirt_volume.XMLDesc(0)
        assert xml == """<volume type='file'>
  <name>test_env_test_node_test_volume</name>
  <key>/default-pool/test_env_test_node_test_volume</key>
  <source>
  </source>
  <capacity unit='bytes'>549755813888</capacity>
  <allocation unit='bytes'>549755813888</allocation>
  <target>
    <path>/default-pool/test_env_test_node_test_volume</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0644</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
</volume>
"""
        volume.erase()

        assert not volume.exists()

    @pytest.mark.xfail(reason="need libvirtd >= 1.2.12")
    def test_child(self):
        volume = self.node.add_volume(
            name='test_volume',
            capacity=512,
        )

        volume.define()

        child = volume.create_child('test_child')

        child.define()

        assert child.capacity == 512
        assert child.get_capacity() == 549755813888
        assert child.get_path() == (
            '/default-pool/test_env_test_node_test_child')
        assert child.get_allocation() == 549755813888

        xml = child._libvirt_volume.XMLDesc(0)

        assert xml == """<volume type='file'>
  <name>test_env_test_node_test_child</name>
  <key>/default-pool/test_env_test_node_test_child</key>
  <source>
  </source>
  <capacity unit='bytes'>549755813888</capacity>
  <allocation unit='bytes'>549755813888</allocation>
  <target>
    <path>/default-pool/test_env_test_node_test_child</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0644</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
  <backingStore>
    <path>/default-pool/test_env_test_node_test_volume</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0644</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </backingStore>
</volume>
"""

    def test_source_image(self):
        volume = self.node.add_volume(
            name='test_volume',
            source_image='/tmp/admin.iso',
        )

        volume.define()

        assert volume.capacity is None
        assert volume.get_capacity() == 5368709120
        assert volume.get_format() == 'qcow2'
        assert volume.get_path() == (
            '/default-pool/test_env_test_node_test_volume')
        assert volume.exists()

    def test_upload(self):
        volume = self.node.add_volume(
            name='test_volume',
            source_image='/tmp/admin.iso',
        )

        volume.define()
        assert volume.capacity is None
        assert volume.get_format() == 'qcow2'

        volume.upload('/tmp/admin.iso')
        assert self.libvirt_vol_resize_mock.called is False
        self.libvirt_vol_up_mock.assert_has_calls((
            mock.call(flags=0, length=5368709120, offset=0, stream=mock.ANY),
            mock.call(flags=0, length=5368709120, offset=0, stream=mock.ANY),
        ))
        assert volume.capacity is None
        assert volume.get_format() == 'qcow2'

    def test_upload_resize(self):
        volume = self.node.add_volume(
            name='test_volume',
            source_image='/tmp/admin.iso',
        )

        volume.define()
        assert volume.capacity is None
        assert volume.get_format() == 'qcow2'

        volume.upload('/tmp/admin2.iso')
        self.libvirt_vol_resize_mock.assert_called_once_with(6442000000)
        assert volume.capacity is None
