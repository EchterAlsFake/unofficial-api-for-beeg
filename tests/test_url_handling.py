"""Offline regressions for URL identity, edge cases, and parsing contracts."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from beeg_api import beeg_api as api
from beeg_api.modules.errors import NotFound


class UrlHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_keeps_trailing_zero_and_ignores_url_syntax(self):
        urls = (
            "https://beeg.com/-012340?t=4-60",
            "https://beeg.com/-012340/",
            "https://beeg.com/video/12340",
            "12340",
            "-012340",
            "beeg.com/-012340",
            "https://beeg.com/BigTits/-012340",
            "https://beeg.com/-012340/sample-slug",
        )
        for url in urls:
            fetch = AsyncMock(
                side_effect=[
                    json.dumps({"file": {"data": [{"cd_value": "Example", "id": 1}], "fl_duration": 2}}),
                    "example.m3u8",
                ]
            )
            with patch.object(api, "get_html_content", fetch):
                result = await api.Video(url=url, core=object())._load_api()
            self.assertEqual(result["key"], "12340", f"Failed for url: {url}")
            self.assertEqual(
                fetch.call_args_list[0].kwargs["url"],
                "https://store.externulls.com/facts/file/12340",
                f"Incorrect facts URL for: {url}",
            )

    def test_extract_key_all_formats(self):
        cases = {
            "https://beeg.com/-0830673897358738": "830673897358738",
            "https://beeg.com/-830673897358738": "830673897358738",
            "https://beeg.com/830673897358738": "830673897358738",
            "https://beeg.com/video/830673897358738": "830673897358738",
            "https://beeg.com/video/-830673897358738": "830673897358738",
            "https://beeg.com/video/-0830673897358738": "830673897358738",
            "https://beeg.com/BigTits/-0830673897358738": "830673897358738",
            "https://beeg.com/tag/big-tits/-0830673897358738": "830673897358738",
            "https://beeg.com/-0830673897358738/tangled-hearts": "830673897358738",
            "https://beeg.com/BigTits/-0830673897358738/tangled-hearts": "830673897358738",
            "https://www.beeg.com/-0830673897358738": "830673897358738",
            "http://beeg.com/-0830673897358738": "830673897358738",
            "//beeg.com/-0830673897358738": "830673897358738",
            "beeg.com/-0830673897358738": "830673897358738",
            "www.beeg.com/-0830673897358738": "830673897358738",
            "-0830673897358738": "830673897358738",
            "830673897358738": "830673897358738",
            "https://beeg.com/-0830673897358738?t=100&utm_source=test": "830673897358738",
            "https://beeg.com/-0830673897358738#time=100": "830673897358738",
            "https://beeg.com/-0830673897358738/": "830673897358738",
            "  https://beeg.com/-0830673897358738 \n\t": "830673897358738",
            "0": "0",
            "-0": "0",
            "https://beeg.com/-0": "0",
        }
        for url, expected in cases.items():
            self.assertEqual(api.extract_key(url), expected, f"Failed for {url}")

    def test_extract_key_invalid(self):
        invalid_inputs = [
            "",
            "   ",
            "https://google.com/12345",
            "https://beeg.com/",
            "https://beeg.com/BigTits",
            "https://beeg.com/tag/asian",
            "https://beeg.com/about",
            "random text",
        ]
        for url in invalid_inputs:
            with self.assertRaises(ValueError, msg=f"Should raise ValueError for {url}"):
                api.extract_key(url)

    async def test_load_api_metadata_fields(self):
        payload = {
            "file": {
                "id": 99999,
                "data": [{"cd_value": "Super Title", "id": 1234}],
                "fl_duration": 600,
            },
            "tags": [
                {"tg_name": "Performer Girl", "is_owner": True, "is_person": True},
                {"tg_name": "{Big} Tits", "is_owner": False, "is_person": False},
            ],
            "fc_facts": [
                {"fc_thumbs": [42], "fc_created": "2026-01-01T00:00:00Z"},
            ],
        }
        fetch = AsyncMock(
            side_effect=[
                json.dumps(payload),
                "key=xyz/media.m3u8",
            ]
        )
        with patch.object(api, "get_html_content", fetch):
            res = await api.Video(url="https://beeg.com/-099999", core=object())._load_api()

        self.assertEqual(res["title"], "Super Title")
        self.assertEqual(res["video_id"], 1234)
        self.assertEqual(res["duration"], 600)
        self.assertEqual(res["m3u8_base_url"], "https://video.beeg.com/key=xyz/media.m3u8")
        self.assertEqual(res["author"], "Performer Girl")
        self.assertEqual(res["tags"], ["Performer Girl", "Big Tits"])
        self.assertEqual(res["thumbnail"], "https://thumbs.externulls.com/videos/99999/42.webp")
        self.assertEqual(res["publish_date"], "2026-01-01T00:00:00Z")

    async def test_load_api_corrupt_or_missing_json(self):
        test_cases = [
            "not a json",
            json.dumps({"file": None}),
            json.dumps({"file": {"data": []}}),
            json.dumps("some string"),
        ]
        for bad_payload in test_cases:
            fetch = AsyncMock(return_value=bad_payload)
            with patch.object(api, "get_html_content", fetch):
                with self.assertRaises(NotFound):
                    await api.Video(url="https://beeg.com/-0123", core=object())._load_api()


if __name__ == "__main__":
    unittest.main()
