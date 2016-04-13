# encoding: utf-8

import os
import uuid
import shutil
import mimetypes

from .device import BaseDevice


class VfsDevice(BaseDevice):
    def os_path(self, key):
        """ 找到key在操作系统中的地址 """

        # 读取环境变量  VFS_xxx 做为环境变量
        root_path = os.environ['VFS_' + self.name.upper()]

        if '++versions++' in key:
            # 历史版本，直接找到对应的历史版本文件夹
            # ff/aa.doc/++versions++/1.doc -> ff/.frs/aa.doc/archived/1.doc
            key, version = key.split('/++versions++/')
            key = key.split('/')
            key.insert(-1, '.frs')
            key.append('archived')
            key.append(version)
            key = '/'.join(key)
        if os.sep != '/':
            key = key.replace('/', os.sep)
        # key can't be an absolute path
        key = key.lstrip(os.sep)
        return os.path.join(root_path, key)

    def gen_key(self, prefix='', suffix=''):
        """
        使用uuid生成一个未使用的key, 生成随机的两级目录
        :param prefix: 可选前缀
        :param suffix: 可选后缀
        :return: 设备唯一的key
        """
        key = uuid.uuid4().hex
        key = '/'.join((key[:2], key[2:5], key[5:]))
        return prefix + key + suffix

    @staticmethod
    def makedirs(path):
        dir_name = os.path.dirname(path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

    def get_data(self, key, offset=0, size=-1):
        """ 根据key返回文件内容，适合小文件 """
        path = self.os_path(key)
        with open(path, 'rb') as f:
            return f.read()

    def _get_path_from_session(self, session_id):
        key, _ = os.path.split(session_id)
        return self.os_path(key)

    def multiput_new(self, key, size):
        """ 开始一个多次写入会话, 返回会话ID"""
        os_path = self.os_path(key)
        self.makedirs(os_path)
        with open(os_path, 'wb'):
            pass
        return os.path.join(key, str(size))

    def multiput_offset(self, session_id):
        """ 某个文件当前上传位置 """
        return os.path.getsize(self._get_path_from_session(session_id))

    def multiput(self, session_id, data, offset=None):
        """ 从offset处写入数据 """
        os_path = self._get_path_from_session(session_id)
        if offset is None:
            with open(os_path, 'ab') as f:
                f.write(data)
                return f.tell()
        with open(os_path, 'r+b') as f:
            f.seek(offset)
            f.write(data)
            return f.tell()

    def multiput_save(self, session_id):
        """ 某个文件当前上传位置 """
        _, size = os.path.split(session_id)
        if not size.isdigit() or int(size) != self.multiput_offset(session_id):
            raise Exception('File Size Check Failed')

    def multiput_delete(self, session_id):
        """ 删除一个写入会话 """
        os.remove(self._get_path_from_session(session_id))

    def put_data(self, key, data):
        """ 直接存储一个数据，适合小文件 """
        os_path = self.os_path(key)
        self.makedirs(os_path)
        with open(os_path, 'wb') as fd:
            fd.write(data)

    def put_stream(self, key, stream):
        os_path = self.os_path(key)
        self.makedirs(os_path)
        with open(os_path, 'ab') as f:
            shutil.copyfileobj(stream, f)
            return f.tell()

    def remove(self, key):
        """ 删除key文件 """
        os.remove(self.os_path(key))

    def copy_data(self, from_key, to_key):
        src = self.os_path(from_key)
        dst = self.os_path(to_key)
        self.makedirs(dst)
        shutil.copy(src, dst)

    def stat(self, key):
        os_path = self.os_path(key)
        return {
            "fileSize": os.path.getsize(os_path),
            "hash": None,
            "mimeType": mimetypes.guess_type(key)[0],
            "putTime": os.path.getctime(os_path)
        }
