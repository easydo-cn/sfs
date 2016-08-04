# -*- coding: utf-8 -*-
import os
import unittest


from mdfs.aliyun import  AliyunDevice
from mdfs.vfs import VfsDevice


class AliyunTestCase(unittest.TestCase):
    def setUp(self):
        vfs_device = VfsDevice(name="vfs_test_one", title="vfs_test", root_path="C:\\testvfs")
        self.key = u'default.zopen.standalone/e/a/e/1f4e514fe417aa2373c97e7c9cc88.exe'
        self.aliyun_device = AliyunDevice('aliyun_test_one',
                                          title='aliyun_test',
                                          local_device=vfs_device,
                                          access_key_id='3vN0eE9VgjAgKafY',
                                          access_key_secret='lqDKfBQHrq0ovgVB49ICMk1KEselUz',
                                          endpoint='oss-cn-qingdao.aliyuncs.com',
                                          bucket_name='edotest')

    def tearDown(self):
        pass

    def test_1_exists(self):
        key = "ff/.frs/aa.doc/"
        self.assertTrue(
            self.aliyun_device.exists(key)
        )

    def test_2_upload(self):
        local_session_id = self.aliyun_device.multiput_new(self.key)
        offset = 0
        while offset < 400*1024:
            offset = self.aliyun_device.multiput(local_session_id, "a"*500*1024, offset)

        self.aliyun_device.multiput_save(local_session_id)
        self.assertTrue(self.aliyun_device.exists(self.key))

    def test_3_os_path(self):
        ospath = self.aliyun_device.os_path(self.key)
        self.assertIsInstance(ospath, unicode)

    def test_4_copy_data(self):
        to_key = 'ff/.frs/aa.doc/archived/abcd.txt'
        self.aliyun_device.copy_data(self.key, to_key)
        self.assertTrue(self.aliyun_device.exists(to_key))

    #
    # def test_5_remote(self):
    #     self.aliyun_device.remove(self.key)
    #     self.assertFalse(self.aliyun_device.exists(self.key))

    # def test_6_rmdir(self):
    #     key = u'default.zopen.standalone/e/'
    #     self.aliyun_device.rmdir(key)
    #     self.assertFalse(self.aliyun_device.exists(key))

if __name__ == '__main__':
    unittest.main()