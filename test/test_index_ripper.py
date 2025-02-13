import pytest
from unittest.mock import MagicMock, patch
import tkinter as tk
import os
import sys

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from index_ripper import WebsiteCopier


@pytest.fixture
def app():
    with patch("tkinter.Tk") as mock_tk:
        # 模擬 Tk 實例
        mock_tk.return_value = MagicMock()
        app = WebsiteCopier()
        yield app


def test_init(app):
    """測試應用程式初始化"""
    assert hasattr(app, "window")
    assert hasattr(app, "url_entry")
    assert hasattr(app, "tree")
    assert hasattr(app, "files_dict")


def test_filter_file_type(app):
    """測試檔案類型過濾功能"""
    # 模擬檔案類型設置
    app.file_types = {".mp4": tk.BooleanVar(value=True)}

    # 測試支援的檔案類型
    assert app.filter_file_type("test.mp4") == True

    # 測試不支援的檔案類型
    assert app.filter_file_type("test.txt") == False


def test_create_folder_structure(app):
    """測試資料夾結構創建"""
    # 模擬必要的屬性
    app.folders = {}
    app.tree = MagicMock()

    # 測試基本路徑
    parent_id = app.create_folder_structure("test/folder", "http://example.com")
    assert len(app.folders) > 0

    # 測試空路徑
    empty_id = app.create_folder_structure("", "http://example.com")
    assert empty_id == ""


def test_update_file_types(app):
    """測試檔案類型更新功能"""
    app.file_types = {}
    app.file_type_counts = {}
    app.window = MagicMock()

    # 測試新檔案類型
    app.update_file_types("test.mp4")
    assert ".mp4" in app.file_types
    assert app.file_type_counts[".mp4"] == 1

    # 測試現有檔案類型
    app.update_file_types("another.mp4")
    assert app.file_type_counts[".mp4"] == 2
