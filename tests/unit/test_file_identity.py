import os
from pathlib import Path

import pytest

from cdrive_cleaner.windows.file_identity import file_reference


def test_file_reference_distinguishes_files_and_matches_hardlinks(tmp_path: Path) -> None:
    first, second, linked = tmp_path / "first", tmp_path / "second", tmp_path / "linked"
    first.write_text("a")
    second.write_text("b")
    first_ref = file_reference(first)
    second_ref = file_reference(second)
    assert (first_ref.volume, first_ref.index) != (second_ref.volume, second_ref.index)
    try:
        os.link(first, linked)
    except OSError:
        pytest.skip("hard links unavailable")
    first_ref, linked_ref = file_reference(first), file_reference(linked)
    assert (first_ref.volume, first_ref.index) == (linked_ref.volume, linked_ref.index)
    assert first_ref.link_count >= 2
