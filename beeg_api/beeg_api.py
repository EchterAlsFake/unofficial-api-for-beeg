from __future__ import annotations

import logging
import json
import os
import re
from urllib.parse import urlsplit

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


def extract_key(url: str) -> str:
    """Extract and validate the numeric video ID/key from a Beeg URL or raw ID string."""
    raw_url = str(url).strip()
    if not raw_url:
        raise ValueError("A Beeg video URL with a numeric ID is required")

    # Direct numeric or hyphen-prefixed numeric string (e.g. "830673897358738" or "-0830673897358738")
    if re.fullmatch(r"-?\d+", raw_url):
        return raw_url.lstrip("-").lstrip("0") or "0"

    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"
    elif raw_url.startswith(("beeg.com/", "www.beeg.com/")):
        raw_url = f"https://{raw_url}"

    parsed = urlsplit(raw_url)
    if parsed.netloc and not re.search(r"(?:^|\.)beeg\.com$", parsed.netloc, re.IGNORECASE):
        raise ValueError("A Beeg video URL with a numeric ID is required")

    path = parsed.path.rstrip("/")

    # 1. Segment starting with minus: /-0123 or /-123 (supports tag/title paths like /-0123/title)
    match = re.search(r"/-0*(\d+)(?:/|$)", path)
    if match:
        return match.group(1).lstrip("0") or "0"

    # 2. Segment after /video/: /video/123 or /video/-123
    match = re.search(r"/video/-?0*(\d+)(?:/|$)", path)
    if match:
        return match.group(1).lstrip("0") or "0"

    # 3. Path ending in numeric segment: /12345 or /.../12345
    match = re.search(r"/0*(\d+)$", path)
    if match:
        return match.group(1).lstrip("0") or "0"

    raise ValueError("A Beeg video URL with a numeric ID is required")


async def get_html_content(core: BaseCore, url: str, *, owner=None) -> str:
    return await fetch_content(core, url, logger=logger, owner=owner,
                               error_types=provider_errors)


@dataclass(slots=True, kw_only=True)
class Video(BaseMedia):
    url: str
    core: BaseCore
    title: str | None = media_field("api")
    video_id: int | str | None = media_field("api")
    duration: int | None = media_field("api")
    m3u8_base_url: str | None = media_field("api")
    key: str | None = media_field("api")
    tags: list[str] | None = media_field("api")
    thumbnail: str | None = media_field("api")
    author: str | None = media_field("api")
    publish_date: str | None = media_field("api")

    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api"}

    async def _load_api(self) -> dict[str, object]:
        """
        Fetches the data from beeg's API and parses it into the dataclass objects
        :return:
        """
        key = extract_key(self.url)

        json_text = await get_html_content(url=f"https://store.externulls.com/facts/file/{key}",
                                           core=self.core, owner=self)
        try:
            json_data = json.loads(json_text)
        except Exception as e:
            raise NotFound(f"Failed to parse video facts for key {key}: {e}") from e

        if not isinstance(json_data, dict):
            raise NotFound(f"Video data not found for key: {key}")

        file_data = json_data.get("file")
        if not file_data or not isinstance(file_data, dict):
            raise NotFound(f"Video file data missing for key: {key}")

        data_records = file_data.get("data")
        if not data_records or not isinstance(data_records, list):
            raise NotFound(f"Video records missing for key: {key}")

        record = data_records[0] if isinstance(data_records[0], dict) else {}

        play_path = await get_html_content(
            url=f"https://store.externulls.com/video/play_url/{key}",
            core=self.core,
            owner=self,
        )
        play_path_clean = play_path.strip().lstrip("/") if isinstance(play_path, str) else ""

        # Extract tags and author if present
        tags_data = json_data.get("tags")
        tags: list[str] | None = None
        author: str | None = None
        if isinstance(tags_data, list):
            tags_list = []
            for t in tags_data:
                if isinstance(t, dict):
                    name = t.get("tg_name")
                    if name and isinstance(name, str):
                        clean = re.sub(r"[{}]", "", name).strip()
                        if clean:
                            tags_list.append(clean)
                        if t.get("is_owner") and not author:
                            author = clean
                        elif t.get("is_person") and not author:
                            author = clean
            tags = tags_list

        # Extract thumbnail and publish date from fc_facts if present
        thumbnail: str | None = None
        publish_date: str | None = None
        fc_facts = json_data.get("fc_facts")
        if isinstance(fc_facts, list) and fc_facts:
            first_fact = fc_facts[0] if isinstance(fc_facts[0], dict) else {}
            thumbs = first_fact.get("fc_thumbs")
            offset = thumbs[0] if isinstance(thumbs, list) and thumbs else 0
            thumbnail = f"https://thumbs.externulls.com/videos/{key}/{offset}.webp"
            publish_date = first_fact.get("fc_created")

        return {
            "title": record.get("cd_value"),
            "video_id": record.get("id"),
            "duration": file_data.get("fl_duration"),
            "m3u8_base_url": f"https://video.beeg.com/{play_path_clean}" if play_path_clean else None,
            "key": key,
            "tags": tags,
            "thumbnail": thumbnail,
            "author": author,
            "publish_date": publish_date,
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
        if not os.path.isfile(args.file):
            print(f"Error: File not found: {args.file}")
            return
        with open(args.file, "r") as f:
            urls.extend([line.strip() for line in f if line.strip() and not line.strip().startswith("#")])

    if not urls:
        parser.print_help()
        return

    # Ensure output target directory exists
    if not no_title:
        os.makedirs(args.output, exist_ok=True)
    else:
        parent_dir = os.path.dirname(os.path.abspath(args.output))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

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
