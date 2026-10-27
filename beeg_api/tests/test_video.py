import pytest
import tempfile
import os
from ..beeg_api import Client, Video
from base_api import BaseCore
from base_api.modules.config import RuntimeConfig, DownloadConfigHLS
from base_api.modules.errors import DataNotLoadedError, MediaLoadError, NotFound

config = RuntimeConfig()
config.videos_concurrency = 1
config.pages_concurrency = 1
core = BaseCore(configuration=config)


@pytest.mark.asyncio
async def test_all_metadata_and_download():
    client = Client(core=core)
    video = await client.get_video("https://beeg.com/-0830673897358738")
    assert isinstance(video.title, str) and len(video.title) > 0
    assert isinstance(video.m3u8_base_url, str) and len(video.m3u8_base_url) > 0
    assert isinstance(video.video_id, (int, str)) and len(str(video.video_id)) > 0
    assert isinstance(video.key, str) and len(video.key) > 0
    assert isinstance(video.duration, int)
    assert isinstance(video.tags, list) and len(video.tags) > 0
    assert isinstance(video.thumbnail, str) and video.thumbnail.startswith("https://thumbs.externulls.com/")
    assert isinstance(video.author, str) and len(video.author) > 0
    assert isinstance(video.publish_date, str) and len(video.publish_date) > 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_hls = DownloadConfigHLS(quality="worst", path=tmp_dir, return_report=True)
        stuff = await video.download(config_hls)
        assert getattr(stuff, "status", None) == "completed"


@pytest.mark.asyncio
async def test_porn_fetch_target_video():
    """Tests the exact URL used by Porn_Fetch diagnostics and selftests."""
    client = Client(core=core)
    video = await client.get_video("https://beeg.com/-0785353135636417")
    assert video.title == "Executive Reconsiders Employee Dismissal"
    assert video.key == "785353135636417"
    assert video.duration == 924
    assert video.author == "Comatozze"
    assert "Office" in video.tags
    assert video.m3u8_base_url.startswith("https://video.beeg.com/")


@pytest.mark.asyncio
async def test_tag_scoped_and_slug_urls():
    """Verify category/tag scoped and slug appended URLs work seamlessly."""
    client = Client(core=core)

    # Tag-scoped URL (common when copying from Beeg tag/category page)
    v1 = await client.get_video("https://beeg.com/BigTits/-0830673897358738")
    assert v1.key == "830673897358738"
    assert v1.title is not None

    # Title-slug appended URL
    v2 = await client.get_video("https://beeg.com/-0830673897358738/tangled-hearts")
    assert v2.key == "830673897358738"

    # Raw ID without scheme
    v3 = await client.get_video("830673897358738")
    assert v3.key == "830673897358738"


@pytest.mark.asyncio
async def test_lazy_loading_behavior():
    """Test load_api=False lazy loading contract."""
    client = Client(core=core)
    video = await client.get_video("https://beeg.com/-0830673897358738", load_api=False)

    # Accessing unloaded attribute directly raises DataNotLoadedError
    with pytest.raises(DataNotLoadedError):
        _ = video.title

    await video.load_sources("api")
    assert isinstance(video.title, str) and len(video.title) > 0


@pytest.mark.asyncio
async def test_non_existent_video_not_found():
    """Verify non-existent video properly signals NotFound."""
    client = Client(core=core)
    with pytest.raises(MediaLoadError) as exc_info:
        await client.get_video("https://beeg.com/-999999999999999")
    assert isinstance(exc_info.value.__cause__, NotFound)


@pytest.mark.asyncio
async def test_download_auto_loads_unloaded_video():
    """Verify video.download() triggers automatic source loading if not already loaded."""
    client = Client(core=core)
    video = await client.get_video("https://beeg.com/-0830673897358738", load_api=False)
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_hls = DownloadConfigHLS(quality="worst", path=tmp_dir, return_report=True)
        report = await video.download(config_hls)
        assert getattr(report, "status", None) == "completed"
        assert video.title is not None
