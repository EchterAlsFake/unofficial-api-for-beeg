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
import asyncio
import json
import logging
from dataclasses import dataclass

from curl_cffi import Response
from functools import cached_property
from base_api.modules.type_hints import DownloadReport
from base_api import BaseCore, setup_logger, DownloadConfigHLS
from base_api.modules.errors import InvalidProxy, BotProtectionDetected, UnknownError, NetworkRequestError
from beeg_api.modules.errors import NetworkError, NotFound, UnknownNetworkError, BotDetection, ProxyError, DownloadFailed


async def get_html_content(core: BaseCore, url: str) -> str | None | dict:
    # What should I do here?
    try:
        content = await core.fetch(url)
        if isinstance(content, str):
            return content

        if isinstance(content, Response):
            if content.status_code == 404:
                raise NotFound(f"Server returned 404 for: {url}")

    except NetworkRequestError as e:
        raise NetworkError(str(e)) from e

    except InvalidProxy as e:
        raise ProxyError(str(e)) from e

    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e

    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


@dataclass(slots=True)
class VideoMetadata:
    title: str
    key: str
    video_id: str
    duration: int
    m3u8_base_url: str


class Video:
    __slots__ = ("metadata", "core")
    def __init__(self, metadata: VideoMetadata, core: BaseCore):
        self.metadata = metadata
        self.core = core


    @property
    def title(self) -> str:
        return self.metadata.title

    @property
    def key(self) -> str:
        return self.metadata.key

    @property
    def video_id(self) -> str:
        return self.metadata.video_id

    @property
    def duration(self) -> int:
        return self.metadata.duration

    @property
    def m3u8_base_url(self) -> str:
        return self.metadata.m3u8_base_url

    async def download(self, configuration: DownloadConfigHLS) -> bool | DownloadReport:
        """
        :param configuration:
        :return:
        """
        if not configuration.no_title:
            configuration.path = os.path.join(configuration.path, f"{self.title}.mp4")

        configuration.m3u8_base_url = self.m3u8_base_url

        try:
            return await self.core.download(configuration)

        except Exception as e:
            raise DownloadFailed(str(e))


class VideoBuilder:
    def __init__(self, url: str, core: BaseCore, json_data: dict | None = None):
        self.url = url
        self.core = core
        self.json_data = json_data
        self.logger = setup_logger(name="BEEG API - [Video]", log_file=None, level=logging.ERROR)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.clean()

    def _from_html(self):
        meta = VideoMetadata(
            title=self.title,
            key=self.key,
            video_id=self.video_id,
            duration=self.duration,
            m3u8_base_url=self.m3u8_base_url,

        )

        return Video(meta, self.core)


    async def clean(self):
        self.json_data = None
        self.url = None
        self.core = None
        self.logger = None

    async def init(self):
        if not self.json_data:
            self.json_data = await get_html_content(url=f"https://store.externulls.com/facts/file/{self.key}",
                                                    core=self.core)

            assert isinstance(self.json_data, str)
            self.json_data = json.loads(self.json_data)

        return await asyncio.to_thread(self._from_html)

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None, log_port: int | None = None):
        if not level:
            level = logging.DEBUG
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


class Client:
    def __init__(self, core: BaseCore = BaseCore()):
        self.core = core
        self.core.initialize_session()

    async def get_video(self, url: str) -> Video:
        return await VideoBuilder(url, core=self.core).init()

