"""The CLI entry point."""
import pytest

from tickr.cli import main


@pytest.mark.turn("t1_scaffold")
def test_main_with_no_arguments_returns_zero():
    assert main([]) == 0


@pytest.mark.turn("t1_scaffold")
def test_main_prints_a_summary(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.strip() != ""
