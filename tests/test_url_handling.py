"""Offline regressions for URL identity, pagination and listing contracts."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from beeg_api import beeg_api as api


class EmptyStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class UrlHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_keeps_trailing_zero_and_ignores_url_syntax(self):
        for url in ("https://beeg.com/-012340?t=4-60", "https://beeg.com/-012340/", "https://beeg.com/video/12340"):
            fetch = AsyncMock(
                side_effect=[
                    json.dumps({"file": {"data": [{"cd_value": "Example", "id": 1}], "fl_duration": 2}}),
                    "example.m3u8",
                ]
            )
            with patch.object(api, "get_html_content", fetch):
                result = await api.Video(url=url, core=object())._load_api()
            self.assertEqual(result["key"], "12340")
            self.assertEqual(fetch.call_args_list[0].kwargs["url"], "https://store.externulls.com/facts/file/12340")


if __name__ == "__main__":
    unittest.main()
