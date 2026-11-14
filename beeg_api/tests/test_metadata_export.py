import json
import unittest
from unittest.mock import AsyncMock, patch

from beeg_api.beeg_api import Video


class MetadataExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_and_person_roles_are_not_collapsed(self):
        data = {"file": {"data": [{"id": 1, "cd_value": "Example"}], "fl_duration": 60},
                "tags": [{"tg_name": "Person", "is_person": True}, {"tg_name": "Owner", "is_owner": True}]}
        source = Video(url="https://beeg.com/-123", core=None)
        with patch("beeg_api.beeg_api.get_html_content", AsyncMock(side_effect=[json.dumps(data), "example.m3u8"])):
            fields = await source._load_api()
        self.assertEqual(fields["people"], ["Person"])
        self.assertEqual(fields["owners"], ["Owner"])
