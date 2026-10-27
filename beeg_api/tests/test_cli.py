import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from beeg_api.beeg_api import create_parser, run_main, main


class TestCLI(unittest.IsolatedAsyncioTestCase):
    def test_parser_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["--output", "/tmp/out"])
        self.assertEqual(args.quality, "best")
        self.assertEqual(args.no_title, "False")
        self.assertEqual(args.output, "/tmp/out")
        self.assertIsNone(args.download)
        self.assertIsNone(args.file)

    def test_parser_custom_args(self):
        parser = create_parser()
        args = parser.parse_args([
            "--download", "https://beeg.com/12345",
            "--output", "/tmp/out",
            "--quality", "worst",
            "--no-title", "True"
        ])
        self.assertEqual(args.download, "https://beeg.com/12345")
        self.assertEqual(args.output, "/tmp/out")
        self.assertEqual(args.quality, "worst")
        self.assertEqual(args.no_title, "True")

    def test_parser_no_title_flag(self):
        parser = create_parser()
        args = parser.parse_args(["--output", "/tmp/out", "--no-title"])
        self.assertEqual(args.no_title, "True")

    async def test_run_main_download(self):
        mock_video = MagicMock()
        mock_video.title = "Sample Video"
        mock_video.download = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_video = AsyncMock(return_value=mock_video)

        with patch("beeg_api.beeg_api.Client", return_value=mock_client):
            await run_main(["--download", "https://beeg.com/12345", "--output", "/tmp/out"])

        mock_client.get_video.assert_awaited_once_with("https://beeg.com/12345")
        mock_video.download.assert_awaited_once()

    async def test_run_main_file(self):
        mock_video = MagicMock()
        mock_video.title = "Sample Video"
        mock_video.download = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_video = AsyncMock(return_value=mock_video)

        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("# comment\nhttps://beeg.com/1\n\n# another comment\nhttps://beeg.com/2\n")
            f.flush()
            temp_name = f.name

        try:
            with patch("beeg_api.beeg_api.Client", return_value=mock_client):
                await run_main(["--file", temp_name, "--output", "/tmp/out"])

            self.assertEqual(mock_client.get_video.await_count, 2)
            self.assertEqual(mock_video.download.await_count, 2)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

    async def test_run_main_missing_file(self):
        # Should not crash on non-existent file
        await run_main(["--file", "/tmp/nonexistent_urls_file_12345.txt", "--output", "/tmp/out"])

    async def test_run_main_no_urls(self):
        # Should not crash when no download or file is provided
        await run_main(["--output", "/tmp/out"])

    async def test_run_main_creates_missing_directory(self):
        mock_video = MagicMock()
        mock_video.title = "Sample"
        mock_video.download = AsyncMock()

        mock_client = MagicMock()
        mock_client.get_video = AsyncMock(return_value=mock_video)

        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_output = os.path.join(tmp_dir, "nested", "downloads")
            self.assertFalse(os.path.exists(nested_output))

            with patch("beeg_api.beeg_api.Client", return_value=mock_client):
                await run_main(["--download", "https://beeg.com/12345", "--output", nested_output])

            self.assertTrue(os.path.isdir(nested_output))

    async def test_real_download(self):
        """Integration test: verifies real video download via CLI into newly created output directory."""
        url = "https://beeg.com/-0830673897358738"
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_sub = os.path.join(tmp_dir, "beeg_dl")
            await run_main(["--download", url, "--output", target_sub, "--quality", "worst"])
            files = [f for f in os.listdir(target_sub) if not f.endswith(".tmp")]
            self.assertTrue(len(files) > 0, "Expected downloaded video file in output directory")


if __name__ == "__main__":
    unittest.main()
