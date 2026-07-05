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
import json
import asyncio
import logging
from logging import Logger
from dataclasses import dataclass

from curl_cffi import Response
from base_api.modules.type_hints import DownloadReport
from base_api import BaseCore, setup_logger, DownloadConfigHLS, BaseMedia
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

        if not content.ok:
            raise NetworkError(f"Server returned HTTP: {content.status_code}")

        return content.text

    except NetworkRequestError as e:
        raise NetworkError(str(e)) from e

    except InvalidProxy as e:
        raise ProxyError(str(e)) from e

    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e

    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


@dataclass(slots=True, kw_only=True)
class Video(BaseMedia):
    url: str
    core: BaseCore
    logger: None | Logger = None
    title: str | None = None
    video_id: str | None = None
    duration: int | None = None
    m3u8_base_url: str | None = None
    key: str | None = None

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None, log_port: int | None = None):
        if not level:
            level = logging.DEBUG
        self.logger = setup_logger(name="BEEG API - [Video]", log_file=log_file, level=level, http_ip=log_ip,
                                   http_port=log_port)


    async def _perform_load(self, api: bool, html: bool, anything_else: bool):
        # I know this seems as if this doesn't make sense, but it does, trust the process!
        await asyncio.gather(self._fetch_api())

    async def _fetch_api(self) -> None:
        """
        Fetches the data from beeg's API and parses it into the dataclass objects
        :return:
        """

        self.key = self.url.split("/")[-1].strip("-0")  # The video key used across the page for all APIs

        json_data = await get_html_content(url=f"https://store.externulls.com/facts/file/{self.key}",
                                                core=self.core)
        assert isinstance(json_data, str)
        json_data = json.loads(json_data)
        # Usually I'd offload to a thread here, but for 50kb of json we don't need the 5 microseconds lol

        self.title = json_data.get("file").get("data")[0].get("cd_value")
        self.video_id = json_data.get("file").get("data")[0].get("id")
        self.duration = json_data.get("file").get("fl_duration")
        url = json_data.get("file").get("hls_resources").get("fl_cdn_multi")
        self.m3u8_base_url = f"https://video.externulls.com/{url}"

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


class Client:
    def __init__(self, core: BaseCore = BaseCore()):
        self.core = core
        self.core.initialize_session()

    async def get_video(self, url: str, load_api: bool = True):
        video = Video(url=url, core=self.core)
        return await video.load(api=load_api)

