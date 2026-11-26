from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, replace
from http.cookiejar import CookieJar
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote, urlencode, urlsplit

from base_api import BaseCore, CachePolicy, PageInfo, ScrapeStream, make_iterator_config, paginated_stream
from base_api.modules.config import IteratorConfig
from base_api.modules.errors import AccessDeniedError, HTTPStatusError, NetworkError

from beeg_api.modules.errors import AuthenticationError

if TYPE_CHECKING:
    from beeg_api.beeg_api import Video


_SITE = "https://beeg.com"
_AUTH_HOST = "auth.beeg.com"
_STORE_HOST = "store.externulls.com"
_ORIGIN = {"Origin": _SITE}
_PAGE_SIZE = 48
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._~+/=-]+")

PageCount = int | Literal["all"]


def _get_refresh_token(cookies: CookieJar | Mapping[str, str]) -> str:
    if isinstance(cookies, CookieJar):
        candidates = (
            cookie.value
            for cookie in cookies
            if cookie.name == "refreshToken"
            and cookie.domain.lstrip(".") in {_AUTH_HOST, "beeg.com"}
            and cookie.path == "/"
            and not cookie.is_expired()
        )
        token = next(candidates, None)
    else:
        token = cookies.get("refreshToken")
    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
        raise AuthenticationError("A valid Beeg refreshToken cookie is required. Sign in on beeg.com first.")
    return token


def _load_browser_cookies(browser: str | None) -> CookieJar:
    try:
        import browser_cookie3
    except ImportError as error:
        raise ImportError("Install unofficial-api-for-beeg[browser] to import browser cookies.") from error

    if browser is None:
        return browser_cookie3.load(domain_name=_AUTH_HOST)
    for loader in browser_cookie3.all_browsers:
        if loader.__name__ == browser.lower():
            return loader(domain_name=_AUTH_HOST)
    raise ValueError(f"Unsupported browser: {browser}")


@dataclass(frozen=True, slots=True)
class FollowedCreator:
    id: int
    name: str
    slug: str
    kind: Literal["human", "productions"]

    @property
    def url(self) -> str:
        return f"{_SITE}/{quote(self.slug, safe='')}"


class _AccountPages:
    """Supply authenticated page requests to the shared pagination helper."""

    def __init__(self, account: Account) -> None:
        self.account = account
        self.configuration = account._core.configuration

    async def fetch_text(self, url: str, *, method: str) -> str:
        return await self.account._fetch_store(url, method=method)


def _video_rows(content: str) -> list[dict[str, str]]:
    try:
        rows = json.loads(content)
        if not isinstance(rows, list):
            raise ValueError("Expected an array of videos")
        videos = []
        for row in rows:
            file_id = row["file"]["id"]
            if type(file_id) is not int or file_id < 1:
                raise ValueError("Invalid video file ID")
            videos.append({"url": f"{_SITE}/-0{file_id}"})
        return videos
    except (KeyError, TypeError, ValueError) as error:
        raise NetworkError("Beeg returned an invalid account video listing.") from error


class Account:
    """A read-only Beeg account session with automatic access-token renewal."""

    def __init__(self, core: BaseCore, cookies: CookieJar | Mapping[str, str]) -> None:
        self._core = core
        self._refresh_token = _get_refresh_token(cookies)
        self._access_token: str | None = None
        self._refresh_lock = asyncio.Lock()

    async def _refresh(self, previous_token: str | None = None) -> str:
        async with self._refresh_lock:
            if self._access_token is not None and self._access_token != previous_token:
                return self._access_token

            # BaseCore's cookie jar is shared by its requests. Use an isolated
            # core for the refresh response, which sets a rotated cookie.
            config = copy(self._core.configuration)
            config.cookies = None
            async with BaseCore(configuration=config) as auth_core:
                try:
                    response = await auth_core.request(
                        f"https://{_AUTH_HOST}/refresh/",
                        method="POST",
                        headers=_ORIGIN,
                        cookies={"refreshToken": self._refresh_token},
                        allow_redirects=False,
                    )
                except AccessDeniedError as error:
                    raise AuthenticationError("Beeg rejected the session. Sign in on beeg.com again.") from error
                except HTTPStatusError as error:
                    if error.status_code == 400:
                        raise AuthenticationError("Beeg rejected the session. Sign in on beeg.com again.") from error
                    raise

                try:
                    token = response.json()["token"]
                    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
                        raise ValueError("Invalid access token")
                except (KeyError, TypeError, ValueError) as error:
                    raise NetworkError("Beeg returned an invalid login response.") from error

                self._refresh_token = response.cookies.get("refreshToken") or self._refresh_token
                self._access_token = token
                return token

    async def _fetch_store(self, url: str, *, method: str = "GET") -> str:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != _STORE_HOST or method != "GET":
            raise ValueError("Account requests require a Beeg store HTTPS GET endpoint.")

        async def fetch(token: str) -> str:
            return await self._core.fetch_text(
                url,
                headers={**_ORIGIN, "Authorization": f"Bearer {token}"},
                cache_policy=CachePolicy.BYPASS,
                allow_redirects=False,
            )

        token = self._access_token or await self._refresh()
        try:
            return await fetch(token)
        except AccessDeniedError:
            token = await self._refresh(previous_token=token)
        try:
            return await fetch(token)
        except AccessDeniedError as error:
            raise AuthenticationError("Beeg denied access to the account library.") from error

    def _videos(
        self, path: str, pages: PageCount, iterator_config: IteratorConfig | None, start_page: int,
    ) -> ScrapeStream[Video]:
        from beeg_api.beeg_api import Video

        def page_url(page: int) -> str:
            query = urlencode({"limit": _PAGE_SIZE, "offset": (page - 1) * _PAGE_SIZE})
            return f"https://{_STORE_HOST}/{path}?{query}"

        def video_for_row(*, core: _AccountPages, url: str) -> Video:
            return Video(url=url, core=self._core)

        config = iterator_config or make_iterator_config(load_specific_sources=(), extract_in_thread=False)
        return paginated_stream(
            core=_AccountPages(self),
            constructor=video_for_row,
            page_url=page_url,
            item_extractor=_video_rows,
            pages=pages,
            start_page=start_page,
            page_info=lambda _content, _page, rows: PageInfo(terminal=len(rows) < _PAGE_SIZE),
            iterator_config=replace(config, _page_request_method="GET", _item_url_key="url"),
        )

    def get_saved_videos(
        self, pages: PageCount = 1, iterator_config: IteratorConfig | None = None, *, start_page: int = 1,
    ) -> ScrapeStream[Video]:
        return self._videos("saves/videos", pages, iterator_config, start_page)

    def get_liked_videos(
        self, pages: PageCount = 1, iterator_config: IteratorConfig | None = None, *, start_page: int = 1,
    ) -> ScrapeStream[Video]:
        return self._videos("bookmarks/liked/videos", pages, iterator_config, start_page)

    def get_watch_later_videos(
        self, pages: PageCount = 1, iterator_config: IteratorConfig | None = None, *, start_page: int = 1,
    ) -> ScrapeStream[Video]:
        return self._videos("bookmarks/checklater/videos", pages, iterator_config, start_page)

    def get_following_videos(
        self, pages: PageCount = 1, iterator_config: IteratorConfig | None = None, *, start_page: int = 1,
    ) -> ScrapeStream[Video]:
        return self._videos("facts/follow", pages, iterator_config, start_page)

    async def get_followed_creators(self) -> list[FollowedCreator]:
        """Return the performers and studios the account follows."""
        content = await self._fetch_store(f"https://{_STORE_HOST}/follow")
        try:
            groups = json.loads(content)
            creators = []
            kinds: tuple[Literal["human", "productions"], ...] = ("human", "productions")
            for kind in kinds:
                rows = groups[kind]
                if not isinstance(rows, list):
                    raise ValueError("Expected an array of creators")
                for row in rows:
                    creator_id, name, slug = row["id"], row["tg_name"], row["tg_slug"]
                    if type(creator_id) is not int or not isinstance(name, str) or not isinstance(slug, str):
                        raise ValueError("Invalid followed creator")
                    creators.append(FollowedCreator(creator_id, name, slug, kind))
            return creators
        except (KeyError, TypeError, ValueError) as error:
            raise NetworkError("Beeg returned an invalid followed-creator listing.") from error
