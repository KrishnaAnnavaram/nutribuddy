from pathlib import Path

import pytest

from nutribuddy.config import Settings
from nutribuddy.ingest import build_index, load_food_folders
from nutribuddy.service import NutriBuddy
from nutribuddy.synthetic import write_all


@pytest.fixture(scope="session")
def workspace(tmp_path_factory) -> Settings:
    root = tmp_path_factory.mktemp("nb")
    settings = Settings().with_dirs(root / "data", root / "work")
    write_all(settings.data_dir)
    load_food_folders(settings, settings.data_dir / "food_data")
    build_index(settings)
    return settings


@pytest.fixture()
def bot(workspace) -> NutriBuddy:
    return NutriBuddy.from_settings(workspace)


@pytest.fixture(scope="session")
def data_dir(workspace) -> Path:
    return workspace.data_dir
