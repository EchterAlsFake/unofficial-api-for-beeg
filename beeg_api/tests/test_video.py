import pytest
from ..beeg_api import Client
from base_api import BaseCore
from base_api.modules.config import RuntimeConfig, DownloadConfigHLS

config = RuntimeConfig()
config.videos_concurrency = 1
config.pages_concurrency = 1
core = BaseCore(configuration=config)



@pytest.mark.asyncio
async def test_all():
    client = Client(core=core)
    video = await client.get_video("https://beeg.com/-0830673897358738")
    assert isinstance(video.title, str) and len(video.title) > 0
    assert isinstance(video.m3u8_base_url, str) and len(video.m3u8_base_url) > 0
    assert isinstance(video.video_id, int) and len(str(video.video_id)) > 0
    assert isinstance(video.key, str) and len(video.key) > 0
    assert isinstance(video.duration, int)

    config = DownloadConfigHLS(quality="worst", return_report=True)
    stuff = await video.download(config)

    assert stuff.status == "completed"