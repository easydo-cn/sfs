# encoding: utf-8

# refer document: https://help.aliyun.com/document_detail/32030.html?spm=5176.doc32032.6.306.4N1U2T
import os
import mimetypes

import oss2
from oss2 import determine_part_size
from oss2.models import PartInfo

from .device import BaseDevice

# 存储每个文件上传的会话信息
UPLOAD_SESSIONS = {}
# 下载数据块的大小
PART_SIZE = 2* 1024 * 1024
# 上传数据块的大小
BUFFER_SIZE = 400 * 1024


class AliyunDevice(BaseDevice):
    """aliyun device """

    def __init__(self, name, title='', local_device=None, access_key_id ='',
                 access_key_secret='', endpoint='', bucket_name='', options={}):
        self.name = name
        self.title = title
        self.options = options
        self.local_device = local_device
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)

    def os_path(self, key):
        """找到key在操作系统中的地址 """
        os_path = self.local_device.os_path(key)
        if not self.local_device.exists(key):
            # 分段下载到本地Cache
            if not self.exists(key):
                raise Exception("File Not Found")
            session_id = self.local_device.multiput_new(key)
            # 获取下载文件的总大小
            size = self.bucket.head_object(key).content_length
            offset = 0
            while offset < size:
                self.local_device.multiput(session_id, self.get_data(key, offset, PART_SIZE))
                offset += PART_SIZE
            self.local_device.multiput_save(session_id)
        return os_path

    def _get_upload_session(self, session_id):
        """获取upload_session"""
        if not UPLOAD_SESSIONS.has_key(session_id):
            upload_id, key, size = session_id.rsplit(':', 2)
            parts = self.bucket.list_parts(key, upload_id).parts
            part_number = len('parts') + 1
            offset = 0
            for part in parts:
                offset += part.size
            UPLOAD_SESSIONS[session_id] = {
                'parts': parts, 'part_number': part_number,
                'offset': offset, 'buffer': ''
            }
        return UPLOAD_SESSIONS[session_id]

    def gen_key(self, prefix='', suffix=''):
        """
        使用uuid生成一个未使用的key, 生成随机的两级目录
        :param prefix: 可选前缀
        :param suffix: 可选后缀
        :return: 设备唯一的key
        """
        return self.local_device.gen_key(prefix, suffix)

    def exists(self, key):
        """ 判断key是否存在"""
        return os.path.exists(self.local_device.os_path(key)) or \
               self.bucket.object_exists(key)

    def get_data(self, key, offset=0, size=-1):
        """ 根据key返回文件内容，适合小文件 """
        data = self.bucket.get_object(key, byte_range=(offset, offset + size)).read()
        return data

    def multiput_new(self, key, size=-1):
        """开始一个多次上传会话, 返回会话ID"""
        session_id = ':'.join([self.bucket.init_multipart_upload(key).upload_id, key, str(size)])
        UPLOAD_SESSIONS[session_id] = {'parts': [], 'offset': 0, 'part_number': 1, 'buffer': ''}
        return session_id

    def multiput_offset(self, session_id):
        """ 某个文件当前上传位置 """
        upload_id, key, size = session_id.rsplit(':', 2)
        if not UPLOAD_SESSIONS.has_key(session_id):
            UPLOAD_SESSIONS[upload_id] = self._get_upload_session(session_id)
        return UPLOAD_SESSIONS[session_id].get('offset')

    def multiput(self, session_id, data, offset=None):
        """ 从offset处上传数据 """
        upload_id, key, size = session_id.rsplit(':', 2)
        upload_session = self._get_upload_session(session_id)
        buffer_data = self._get_buffer_data(upload_session, data, size)
        if buffer_data is not None:
            if upload_session.get('offset') < int(size):
                result = self.bucket.upload_part(key,
                                                 upload_id,
                                                 upload_session.get('part_number'),
                                                 buffer_data
                                                 )
                upload_session['parts'].append(PartInfo(upload_session['part_number'], result.etag))

                upload_session['offset'] += len(buffer_data)
                upload_session['part_number'] += 1
        return upload_session.get('offset')

    def multiput_save(self, session_id):
        """ 某个上传会话当前上传位置 """
        upload_id, key, size = session_id.rsplit(':', 2)
        upload_session = self._get_upload_session(session_id)
        if int(size) != '-1' and upload_session.get('offset') != int(size):
            raise Exception("File Size Check Failed")
        self.bucket.complete_multipart_upload(key, upload_id, upload_session.get('parts'))
        UPLOAD_SESSIONS.pop(session_id)
        return key

    def multiput_delete(self, session_id):
        """ 删除一个上传会话 """
        upload_id, key, size = session_id.rsplit(':', 2)
        upload_session = self._get_upload_session(session_id)
        self.bucket.abort_multipart_upload(key, upload_id)
        UPLOAD_SESSIONS.pop(session_id)

    def remove(self, key):
        """ 删除key文件，本地缓存也删除 """
        if self.local_device.exists(key):
            self.local_device.remove(key)
        self.bucket.delete_object(key)

    def rmdir(self, key):
        """ 删除前缀为key的云端和本地Cache的文件夹"""
        self.local_device.rmdir(key)
        while self.exists(key):
            remove_file_list = [obj.key for obj in oss2.ObjectIterator(self.bucket, prefix=key, max_keys=1000)]
            self.bucket.batch_delete_objects(remove_file_list)


    def copy_data(self, from_key, to_key):
        """复制文件"""
        total_size = self.bucket.head_object(from_key).content_length
        part_size = determine_part_size(total_size, preferred_size=100 * 1024)

        # 初始化分片
        upload_id = self.bucket.init_multipart_upload(to_key).upload_id
        parts = []

        # 逐个分片拷贝
        part_number = 1
        offset = 0
        while offset < total_size:
            num_to_upload = min(part_size, total_size - offset)
            byte_range = (offset, offset + num_to_upload - 1)

            result = self.bucket.upload_part_copy(self.bucket.bucket_name, from_key
                                                  , byte_range, to_key, upload_id, part_number)
            parts.append(PartInfo(part_number, result.etag))
            offset += num_to_upload
            part_number += 1

        # 完成分片上传
        self.bucket.complete_multipart_upload(to_key, upload_id, parts)

    def stat(self, key):
        """ 得到云端文件状态 """
        head_object = self.bucket.head_object(key)
        return {
            "file_size": head_object.content_length,
            "hash": None,
            "mime_type": head_object.content_type,
            "put_time": head_object.last_modified
        }

    def _get_buffer_data(self, upload_session, data, size):
        """进行数据累积 累积长度为BUFFER_SIZE"""
        upload_session['buffer'] += data
        if len(upload_session['buffer']) >= BUFFER_SIZE:
            buffer_data = upload_session['buffer']
            upload_session['buffer'] = ''
            return buffer_data
        elif upload_session['offset'] + len(upload_session['buffer']) >= size:
            return upload_session['buffer']
        else:
            return None
