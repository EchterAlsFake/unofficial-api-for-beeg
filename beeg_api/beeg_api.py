"""
Copyright (C) 2025-2026 Johannes Habel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os
import logging
import threading

from base_api.modules.type_hints import DownloadReport
from curl_cffi import Response
from functools import cached_property
from base_api.base import BaseCore, setup_logger
from base_api.modules.errors import NetworkingError, UnknownError, BotProtectionDetected, InvalidProxy

try:
    from modules.consts import *
    from modules.errors import *
    from modules.errors import *
    from modules.type_hints import callback_type

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.errors import *
    from .modules.type_hints import callback_type
    from .modules.errors import *

try:
    import lxml
    parser = "lxml"

except (ModuleNotFoundError, ImportError):
    parser = "html.parser"


async def get_html_content(core: BaseCore, url: str) -> str | None:
    # What should I do here?
    try:
        content = await core.fetch(url)
        if isinstance(content, str):
            return content

        if isinstance(content, Response):
            if content.status_code == 404:
                raise NotFound(f"Server returned 404 for: {url}")

    except NetworkingError:
        raise NetworkError from NetworkingError

    except InvalidProxy:
        raise ProxyError from InvalidProxy

    except BotProtectionDetected:
        raise BotDetection from BotProtectionDetected

    except UnknownError:
        raise UnknownNetworkError from UnknownError


class Video:
    def __init__(self, url: str, core: BaseCore, json_data: dict | None = None):
        self.url = url
        self.core = core
        self._json_data = json_data
        self.logger = setup_logger(name="BEEG API - [Video]", log_file=None, level=logging.ERROR)

    async def init(self):
        if not self._json_data:
            self._json_data: dict = await self.get_json_content()
            assert isinstance(self._json_data, dict)

        return self

    @property
    def json_data(self) -> dict:
        if not isinstance(self._json_data, dict):
            raise ValueError("You haven't called the init method (probably)")

        return self._json_data

    async def get_json_content(self) -> dict:
        response = await self.core.fetch(f"https://store.externulls.com/facts/file/{self.key}", get_response=True)
        assert isinstance(response, Response)
        return response.json()  # This is the holy grail

    def enable_logging(self, log_file: str = None, level=None, log_ip: str = None, log_port: int = None):
        self.logger = setup_logger(name="BEEG API - [Video]", log_file=log_file, level=level, http_ip=log_ip,
                                   http_port=log_port)

    @cached_property
    def key(self) -> str:
        return self.url.split("/")[-1].strip("-0") # The video key used across the page for all APIs

    @cached_property
    def title(self) -> str:
        return self.json_data.get("file").get("data")[0].get("cd_value")

    @cached_property
    def video_id(self) -> str:
        return self.json_data.get("file").get("data")[0].get("id")

    @cached_property
    def duration(self) -> int:
        return self.json_data.get("file").get("fl_duration")

    @cached_property
    def m3u8_base_url(self) -> str:
        url = self.json_data.get("file").get("hls_resources").get("fl_cdn_multi")
        return f"https://video.externulls.com/{url}"

    async def get_segments(self, quality) -> list:
        """
        :param quality: (str, Quality) The video quality
        :return: (list) A list of segments (the .ts files)
        """
        segments = await self.core.get_segments(quality=quality, m3u8_url_master=self.m3u8_base_url)
        return segments

    async def download(self, quality, path="./", callback: callback_type = None, no_title=False, remux: bool = False,
                 callback_remux=None, start_segment: int = 0, stop_event: threading.Event | None = None,
                 segment_state_path: str | None = None, segment_dir: str | None = None,
                 return_report: bool = False, cleanup_on_stop: bool = True, keep_segment_dir: bool = False
                 ) -> bool | DownloadReport:
        """
        :param callback:
        :param quality:
        :param path:
        :param no_title:
        :param remux:
        :param callback_remux:
        :param start_segment:
        :param stop_event:
        :param segment_state_path:
        :param segment_dir:
        :param return_report:
        :param cleanup_on_stop:
        :param keep_segment_dir:
        :return:
        """
        if not no_title:
            path = os.path.join(path, f"{self.title}.mp4")

        return await self.core.download(video=self, quality=quality, path=path, callback=callback, remux=remux,
                                  callback_remux=callback_remux, start_segment=start_segment, stop_event=stop_event,
                                  segment_state_path=segment_state_path, segment_dir=segment_dir,
                                  return_report=return_report,
                                  cleanup_on_stop=cleanup_on_stop, keep_segment_dir=keep_segment_dir)


class Client:
    def __init__(self, core: BaseCore = BaseCore()):
        self.core = core
        self.core.initialize_session()

    async def get_video(self, url: str) -> Video:
        return await Video(url, core=self.core).init()
