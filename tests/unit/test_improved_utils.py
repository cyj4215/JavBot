"""Tests for improved_utils: download_image_via_curl."""
from unittest.mock import MagicMock, patch

import pytest

from app.improved_utils import download_image_via_curl


class TestDownloadImageViaCurl:
    @patch("app.improved_utils.subprocess.run")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"fake-image-bytes-1024+" + b"x" * 1024
        mock_run.return_value = mock_result

        result = download_image_via_curl("https://javdb.com/avatar.jpg")
        assert result is not None
        assert len(result) > 512
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "curl" in cmd[0]
        assert "https://javdb.com/avatar.jpg" in cmd

    @patch("app.improved_utils.subprocess.run")
    def test_success_with_proxy(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"x" * 1024
        mock_run.return_value = mock_result

        result = download_image_via_curl("https://javdb.com/avatar.jpg", proxy_addr="http://proxy:7890")
        assert result is not None
        cmd = mock_run.call_args[0][0]
        assert "-x" in cmd
        assert "http://proxy:7890" in cmd

    @patch("app.improved_utils.subprocess.run")
    def test_failure_returncode(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 22
        mock_result.stdout = b""
        mock_run.return_value = mock_result

        result = download_image_via_curl("https://javdb.com/avatar.jpg")
        assert result is None

    @patch("app.improved_utils.subprocess.run")
    def test_small_response(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"small"
        mock_run.return_value = mock_result

        result = download_image_via_curl("https://javdb.com/avatar.jpg")
        assert result is None

    @patch("app.improved_utils.subprocess.run")
    def test_timeout_exception(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=25)

        result = download_image_via_curl("https://javdb.com/avatar.jpg")
        assert result is None
