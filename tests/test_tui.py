import synapse.tui as tui


def test_python_tui_launcher_guides_when_node_dependencies_are_missing(monkeypatch, tmp_path, capsys):
    fake_root = tmp_path / "project"
    terminal_ui = fake_root / "terminal-ui"
    terminal_ui.mkdir(parents=True)
    (terminal_ui / "package.json").write_text("{}", encoding="utf-8")
    fake_tui_file = fake_root / "synapse" / "tui.py"
    fake_tui_file.parent.mkdir()
    fake_tui_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(tui, "__file__", str(fake_tui_file))
    tui.run_tui(color=False, unicode_logo=False)

    output = capsys.readouterr().out
    assert "terminal UI dependencies are not installed" in output
    assert "npm install" in output
    assert "python synapse.py --api" in output


def test_python_tui_launcher_runs_npm_when_dependencies_exist(monkeypatch, tmp_path):
    fake_root = tmp_path / "project"
    terminal_ui = fake_root / "terminal-ui"
    node_modules = terminal_ui / "node_modules"
    node_modules.mkdir(parents=True)
    (terminal_ui / "package.json").write_text("{}", encoding="utf-8")
    fake_tui_file = fake_root / "synapse" / "tui.py"
    fake_tui_file.parent.mkdir()
    fake_tui_file.write_text("", encoding="utf-8")
    calls = []

    monkeypatch.setattr(tui, "__file__", str(fake_tui_file))
    monkeypatch.setattr(tui.subprocess, "run", lambda command, cwd, check: calls.append((command, cwd, check)))

    tui.run_tui(color=False, unicode_logo=False)

    assert calls == [(["npm", "start", "--", "--no-color"], terminal_ui, False)]
