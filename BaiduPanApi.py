import requests
import re
import json
import time
import sys
import os
import hashlib

BDPAN = "https://pan.baidu.com"


def set_file_size(file_size):
    for count in ['Bytes', 'KB', 'MB', 'GB']:
        if -1024.0 < file_size < 1024.0:
            return "%3.1f%s" % (file_size, count)
        file_size /= 1024.0
    return "%3.1f%s" % (file_size, 'TB')


# 计算文件md5值 返回梦姬格式秒传链接
# 梦姬格式秒传链接 -> 完整文件md5#前256KB文件md5#文件大小#文件名
def set_file_rapid(file_path):
    print("开始计算文件md5值 文件越大越慢,请耐心等待...")
    print("目标文件 -> %s" % file_path)
    with open(file_path, 'rb') as file:
        file_all_data = file.read()
    with open(file_path, 'rb') as file:
        file_256k_data = file.read(256 * 1024)

    # 完整文件md5
    file_all_md5 = hashlib.md5(file_all_data).hexdigest().upper()
    # 前256KB文件md5
    file_256k_md5 = hashlib.md5(file_256k_data).hexdigest().upper()
    # 文件大小
    file_size = os.path.getsize(file_path)
    # 文件名
    file_name = os.path.basename(file_path)
    # 秒传链接
    return "%s#%s#%s#'%s'" % (file_all_md5, file_256k_md5, file_size, file_name)


class Log:

    def __init__(self, save_in="./log", log_file_name="log_%Y_%m_%d.txt"):
        self.__terminal = sys.stdout
        self.save_in = save_in
        sys.stdout = self
        self.log_file_name = log_file_name

        if not os.path.isdir(self.save_in):
            os.makedirs(self.save_in)
        
        self.__save_in_obj = open(self.set_log_path(), "a", encoding="utf-8")
    
    def __exit__(self):
        self.__save_in_obj.close()
    
    def set_log_path(self):
        return time.strftime(f"{self.save_in}/{self.log_file_name}", time.localtime())
    
    def set_log_style(self, log):
        log_time = time.strftime("%H:%M:%S", time.localtime())
        log_msg = "[%s] %s\n" % (log_time, log)
        return log_msg
    
    def write(self, log):
        if log == "\n" and log.strip() == "":
            return

        log = self.set_log_style(log)
        self.__save_in_obj.write(log)
        self.__save_in_obj.flush()
        self.__terminal.write(log)

    def flush(self):
        self.__terminal.flush()




class bdPan:

    headers = {
        "cookie": "",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    }

    def __init__(self, cookie, log_path="./log", log_file_name="log_%Y_%m_%d.txt"):
        Log(log_path, log_file_name)
        self.bdstoken = None

        self.headers["cookie"] = cookie
        self.get_bdstoken()

    def __link(self, api, data=None, mode="get", json=True, on_bdstoken=True):
        if on_bdstoken:
            if self.bdstoken is None:
                print("bdstoken 未获取请先获取后再调用该 api!")
                return

            if not "?" in api:
                api = f"{api}?bdstoken={self.bdstoken}"
            else:
                api = f"{api}&bdstoken={self.bdstoken}"

        if mode == "get":
            with requests.get(api, data=data, headers=self.headers) as req:
                if json:
                    return req.json()
                
                return req.text

        if mode == "post":
            with requests.post(api, data=data, headers=self.headers) as req:
                if json:
                    return req.json()
                
                return req.text
    
    # 解析秒传链接
    def rapid(self, code):
        return code.split('#', maxsplit=3)

    def get_bdstoken(self):
        """
        获取 bdstoken 用于调用百度网盘 api

        :return: 成功返回数据 失败返回1
        """
        api = BDPAN + "/disk/home"
        user_data = re.findall('locals.mset\\((\\S+?)\\);', self.__link(api, json=False, on_bdstoken=False))
        if not user_data:
            print("bdstoken 获取失败请检查 cookie...")
            return

        self.bdstoken = json.loads(user_data[0])["bdstoken"]

    __status_dir = ""
    def get_dir(self, path, recursion=False):
        """
        获取网盘目录

        :param path: 目录绝对路径
        :param recursion: 递归目录
        :return: 成功返回数据 失败返回错误码
        """

        api = BDPAN + "/api/list"
        data = self.__link(
            api + "?order=time&desc=1&showempty=0&web=1&page=1&num=1000&dir=%s" % path)
        
        if data == None:
            print(f'获取"{path}"目录失败 ...')
        else:
            if data['errno'] != 0:
                print(f'获取"{path}"目录失败 ...')
                print("errno: %s" % data["errno"])

        if not recursion:
            if data != None:
                if data['errno'] == 0:
                    return data['list']
            
            return 
        
        if self.__status_dir == "":
            self.__status_dir = path
        
        for file in data['list']:
            if file["isdir"] == 0:
                continue

            in_dir = file
            in_dir["list"] = self.get_dir(file["path"], recursion=True)
        
        if path == self.__status_dir:
            self.__status_dir = ""
    
    # 使用秒传链接数据转存
    def transfer_rapid(self, rapid, path_name):
        # 解析秒传链接
        rapid_data = self.rapid(rapid)

        # 转存
        api = BDPAN + "/api/rapidupload"
        data = {'path': path_name + '/' + rapid_data[3], 'content-md5': rapid_data[0],
                'slice-md5': rapid_data[1], 'content-length': rapid_data[2]}
        data = self.__link(api, data, "post")

        if data['errno'] == 0:
            print("%s -> %s 链接转存成功!" % (rapid, rapid_data[-1]))
        elif data['errno'] == -8:
            print("%s -> %s 转存失败,目录中已有同名文件存在..." % (rapid, rapid_data[-1]))
        else:
            print("%s -> %s 转存失败,错误码:%s" % (rapid, rapid_data[-1], data['errno']))