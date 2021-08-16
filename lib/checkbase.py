import os
import re
import sys
import traceback
from typing import Any, Callable

import requests
from requests import Response
from requests.utils import add_dict_to_cookiejar

from lib.logger import app_logger as logger
from lib.notify import notify


CI = os.environ.get("CI")
GITHUB_NOTIFICATION = os.environ.get("GITHUB_NOTIFICATION")

RE_COOKIE = re.compile("([^=]+)=\"?(.+?)\"?;\\s*")


class CheckIn(object):
    def __init__(self, title: str, cookies: str, extra_headers=None):
        self.title = title
        self.cookies = cookies
        self.ci = CI
        self.member = None
        self.uid = None
        self.extra_headers = extra_headers

    def _checkin(self,
                 session: requests.Session,
                 get: Callable[[str], Response],
                 post: Callable[[str, Any], Response],
                 info: Callable,
                 error: Callable) -> int:
        error("未重载`_checkin`函数")
        return 255

    @staticmethod
    def chunker(seq, size):
        return (seq[pos:pos + size] for pos in range(0, len(seq), size))

    def checkin(self, cookie: str) -> int:
        self.member = "/"
        self.uid = None
        s = requests.Session()

        cookie_dict = {}
        match = RE_COOKIE.findall(cookie + ";")
        for item in match:
            cookie_dict[item[0]] = item[1]

        add_dict_to_cookiejar(s.cookies, cookie_dict)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/90.0.4430.85 "
                          "Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8,"
                      "application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"
        }

        if self.extra_headers:
            headers.update(self.extra_headers)

        def get(url: str, **kwargs):
            return s.get(url, headers=headers, timeout=20, **kwargs)

        def post(url: str, data=None, **kwargs):
            return s.post(url, data=data, headers=headers, timeout=20, **kwargs)

        prefix = f"[{self.title}]" if self.ci else f"[{self.title}:{self.member}]"

        def info(message: str):
            logger.info(f"{prefix} {message}")

        def error(message: str, *args):
            msg = f"{prefix} {message}"
            logger.error(msg)
            notify(msg, *args)

        return self._checkin(s, get, post, info, error)

    def main(self):
        if not self.cookies:
            logger.info("未配置Cookie，跳过签到")
            return
        ret = 0
        logger.info(f"----------{self.title:8}开始签到----------")
        if "\\n" in self.cookies:
            clist = self.cookies.split("\\n")
        else:
            clist = self.cookies.split("\n")

        for i in range(len(clist)):
            if len(clist) > 1:
                logger.info(f"第{i+1}个账号开始签到")
            try:
                code = self.checkin(clist[i])
                ret |= code if code is not None else 0
            except requests.exceptions.Timeout as e:
                ret |= 1
                notify(f"[{self.title}:Exception]", f"请求超时: {str(e)}")
            except:
                ret |= 1
                logger.error(traceback.format_exc())
                notify(f"[{self.title}:Exception]", traceback.format_exc())
        logger.info(f"----------{self.title:8}签到完毕----------")
        if GITHUB_NOTIFICATION:
            sys.exit(ret)
