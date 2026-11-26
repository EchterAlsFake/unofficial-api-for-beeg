import json
import os

import pytest
from base_api import BaseCore, make_iterator_config

from beeg_api import AuthenticationError, Client, extract_key


@pytest.mark.asyncio
async def test_invalid_refresh_cookie_is_rejected():
    async with BaseCore() as core:
        client = Client(core=core)
        with pytest.raises(AuthenticationError):
            await client.login({"refreshToken": "invalid"})
        assert client.account is None


@pytest.mark.asyncio
async def test_account_libraries_match_live_listings():
    browser = os.environ.get("BEEG_TEST_BROWSER")
    if not browser:
        pytest.skip("Set BEEG_TEST_BROWSER to a browser signed in to Beeg with a like and a followed creator.")

    async with BaseCore() as core:
        client = Client(core=core)
        account = await client.login_from_browser(browser)
        assert client.account is account
        assert core.session is not None
        assert not any(cookie.name == "refreshToken" for cookie in core.session.cookies.jar)
        assert "Authorization" not in core.session.headers

        collections = (
            ("saves/videos", account.get_saved_videos),
            ("bookmarks/liked/videos", account.get_liked_videos),
            ("bookmarks/checklater/videos", account.get_watch_later_videos),
            ("facts/follow", account.get_following_videos),
        )
        for path, collection in collections:
            expected = []
            for offset in (0, 48):
                content = await account._fetch_store(f"https://store.externulls.com/{path}?limit=48&offset={offset}")
                expected.extend(str(row["file"]["id"]) for row in json.loads(content))
            async with collection(pages=2) as stream:
                actual = [extract_key(result.unwrap().url) async for result in stream]
            assert actual == expected
            if collection == account.get_liked_videos:
                assert actual, "The test account needs at least one liked video"

        config = make_iterator_config(load_specific_sources=("api",))
        async with account.get_liked_videos(iterator_config=config) as stream:
            video = (await anext(stream)).unwrap()
            assert video.title and video.key == extract_key(video.url)
            assert video.core is core

        creator_groups = json.loads(await account._fetch_store("https://store.externulls.com/follow"))
        creators = await account.get_followed_creators()
        assert creators, "The test account needs at least one followed creator"
        assert [creator.id for creator in creators] == [
            row["id"] for kind in ("human", "productions") for row in creator_groups[kind]
        ]
