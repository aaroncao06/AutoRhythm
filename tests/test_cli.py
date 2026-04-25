from click.testing import CliRunner

from rapmap.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "RapMap" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_init_requires_args():
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code != 0


def test_syllabify_requires_project():
    runner = CliRunner()
    result = runner.invoke(main, ["syllabify"])
    assert result.exit_code != 0
