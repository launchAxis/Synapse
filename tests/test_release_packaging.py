from pathlib import Path

from scripts.build_release_packages import build_packages


def test_build_packages_creates_platform_split_without_generated_artifacts(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_minimal_source_tree(source)

    packages = build_packages(source, version="0.3.0")

    windows = source
    linux = tmp_path / "Synapse 0.3.0 Linux"
    assert packages == [windows, linux]
    assert (windows / "synapse" / "core.py").exists()
    assert (linux / "synapse" / "core.py").exists()
    assert (windows / "run_synapse.bat").exists()
    assert (windows / "run_tui.bat").exists()
    assert (linux / "run_synapse.sh").exists()
    assert (linux / "run_tui.sh").exists()
    assert (linux / "terminal-ui" / "package.json").exists()
    assert not (linux / "terminal-ui" / "node_modules").exists()
    assert not (windows / "logs").exists()
    assert not (linux / ".pytest_cache").exists()
    assert not list(windows.rglob("*.pyc"))
    assert not list(linux.rglob("*.pyc"))


def test_release_packages_keep_shared_source_identical(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_minimal_source_tree(source)

    build_packages(source, source / "dist", version="0.3.0")

    windows_core = (source / "dist" / "Synapse-0.3.0-Windows" / "synapse" / "core.py").read_text(encoding="utf-8")
    linux_core = (source / "dist" / "Synapse-0.3.0-Linux" / "synapse" / "core.py").read_text(encoding="utf-8")
    assert windows_core == linux_core


def test_explicit_output_dir_still_builds_archive_style_folders(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    make_minimal_source_tree(source)

    packages = build_packages(source, source / "dist", version="0.3.0")

    assert packages == [
        source / "dist" / "Synapse-0.3.0-Windows",
        source / "dist" / "Synapse-0.3.0-Linux",
    ]
    assert (packages[0] / "run_synapse.bat").exists()
    assert (packages[1] / "run_synapse.sh").exists()


def make_minimal_source_tree(source: Path) -> None:
    for filename in [
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "pytest.ini",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-bench.txt",
        "synapse.py",
    ]:
        (source / filename).write_text(filename, encoding="utf-8")

    for dirname in ["synapse", "configs", "benchmarks", "bench", "docs", "tests"]:
        (source / dirname).mkdir()
        (source / dirname / "keep.txt").write_text("keep", encoding="utf-8")

    (source / "synapse" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "logs").mkdir()
    (source / "logs" / "run.txt").write_text("generated", encoding="utf-8")
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "cache.txt").write_text("generated", encoding="utf-8")
    (source / "synapse" / "__pycache__").mkdir()
    (source / "synapse" / "__pycache__" / "core.pyc").write_bytes(b"generated")
    (source / "terminal-ui" / "source").mkdir(parents=True)
    (source / "terminal-ui" / "package.json").write_text("{}", encoding="utf-8")
    (source / "terminal-ui" / "source" / "app.js").write_text("console.log('ok')\n", encoding="utf-8")
    (source / "terminal-ui" / "node_modules").mkdir()
    (source / "terminal-ui" / "node_modules" / "generated.txt").write_text("generated", encoding="utf-8")
