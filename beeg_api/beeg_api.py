from __future__ import annotations

import logging
import json

import argparse

from beeg_api.modules import errors as provider_errors
from base_api.modules.provider import fetch_content, download_errors, download_hls
from base_api.modules.logger import configure_app_logging, get_logger
import asyncio

from dataclasses import dataclass
from typing import ClassVar
from base_api.modules.type_hints import DownloadReport
from base_api import BaseCore, DownloadConfigHLS, BaseMedia, media_field
from base_api.modules.static_functions import str_to_bool
from beeg_api.modules.errors import NetworkError, NotFound, UnknownNetworkError, BotDetection, ProxyError, DownloadFailed


logger = get_logger(__name__)


async def get_html_content(core: BaseCore, url: str, *, owner=None) -> str:
    return await fetch_content(core, url, logger=logger, owner=owner,
                               error_types=provider_errors)


@dataclass(slots=True, kw_only=True)
class Video(BaseMedia):
    url: str
    core: BaseCore
    title: str | None = media_field("api")
    video_id: str | None = media_field("api")
    duration: int | None = media_field("api")
    m3u8_base_url: str | None = media_field("api")
    key: str | None = media_field("api")

    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api"}

    async def _load_api(self) -> dict[str, object]:
        """
        Fetches the data from beeg's API and parses it into the dataclass objects
        :return:
        """

        key = self.url.split("/")[-1].strip("-0")

        json_data = await get_html_content(url=f"https://store.externulls.com/facts/file/{key}",
                                                core=self.core, owner=self)
        json_data = json.loads(json_data)
        # Usually I'd offload to a thread here, but for 50kb of json we don't need the 5 microseconds lol

        file_data = json_data.get("file")
        record = file_data.get("data")[0]
        hls_url = file_data.get("hls_resources").get("fl_cdn_multi")
        return {
            "title": record.get("cd_value"),
            "video_id": record.get("id"),
            "duration": file_data.get("fl_duration"),
            "m3u8_base_url": f"https://video.externulls.com/{hls_url}",
            "key": key,
        }

    @download_errors(DownloadFailed)
    async def download(self, configuration: DownloadConfigHLS) -> bool | DownloadReport:
        return await download_hls(self, configuration)


class Client:
    def __init__(self, core: BaseCore | None = None):
        if core is None:
            core = BaseCore()
        self.core = core
        self.core.initialize_session()

    async def get_video(self, url: str, load_api: bool = True):
        video = Video(url=url, core=self.core)
        if load_api:
            await video.load_sources("api")
        return video


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Beeg API Command Line Interface")
    parser.add_argument("--download", metavar="URL", type=str, help="URL to download from")
    parser.add_argument("--quality", metavar="best|half|worst", type=str, default="best", help="The video quality (best, half, worst)")
    parser.add_argument("--file", metavar="FILE", type=str, help="(Optional) Specify a file with URLs (separated with new lines)")
    parser.add_argument("--output", metavar="DIR", type=str, required=True, help="The output path (with filename or directory)")
    parser.add_argument("--no-title", metavar="True,False", type=str, nargs="?", const="True", default="False",
                        help="Whether to apply video title automatically to output path or not")
    return parser


async def run_main(args_list: list[str] | None = None):
    parser = create_parser()
    args = parser.parse_args(args_list)
    no_title = str_to_bool(args.no_title) if isinstance(args.no_title, str) else bool(args.no_title)
    config = DownloadConfigHLS(quality=args.quality, path=args.output, no_title=no_title)

    urls: list[str] = []
    if args.download:
        urls.append(args.download)
    if args.file:
        with open(args.file, "r") as f:
            urls.extend([line.strip() for line in f if line.strip()])

    if not urls:
        parser.print_help()
        return

    client = Client()
    for url in urls:
        print(f"Fetching video information for: {url}")
        try:
            video = await client.get_video(url)
            title = getattr(video, "title", None) or url
            print(f"Starting download for: {title}")
            await video.download(config)
            print(f"Download complete: {title}")
        except Exception as e:
            logger.exception("CLI failed while processing %s", url)
            print(f"Error downloading {url}: {e}")


def main():
    configure_app_logging(level=logging.INFO)
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")


if __name__ == "__main__":
    main()
