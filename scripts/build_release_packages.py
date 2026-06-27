from __future__ import annotations

import argparse
import os
import shutil
import stat
from pathlib import Path


DEFAULT_VERSION = "0.3.0"
PACKAGE_PLATFORMS = ("Windows", "Linux")

ROOT_FILES = (
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    ".gitattributes",
    "pull_request_template.md",
    "package.json",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-bench.txt",
    "synapse.py",
)

ROOT_DIRS = (
    "synapse",
    "configs",
    "benchmarks",
    "bench",
    "docs",
    "tests",
    "terminal-ui",
)

EXCLUDED_NAMES = {
    ".bench_cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "bench_runs",
    "dist",
    "logs",
    "runs",
    "venv",
    ".venv",
    "env",
    "node_modules",
}

EXCLUDED_SUFFIXES = (".pyc", ".pyo")


def build_packages(
    source_root: Path,
    output_root: Path | None = None,
    version: str = DEFAULT_VERSION,
    dry_run: bool = False,
) -> list[Path]:
    source_root = source_root.resolve()
    packages = package_paths(source_root, output_root, version)

    if dry_run:
        for package in packages:
            print(f"Would build {package}")
        return packages

    for platform, package in zip(PACKAGE_PLATFORMS, packages):
        if package == source_root:
            clean_generated_artifacts(package)
            write_platform_readme(package, platform)
            write_platform_helpers(package, platform)
            continue
        package.parent.mkdir(parents=True, exist_ok=True)
        if package.exists():
            remove_tree(package)
        package.mkdir(parents=True)
        copy_shared_contents(source_root, package)
        write_platform_readme(package, platform)
        write_platform_helpers(package, platform)
    return packages


def package_paths(source_root: Path, output_root: Path | None, version: str) -> list[Path]:
    if output_root is not None:
        root = output_root.resolve()
        return [root / f"Synapse-{version}-{platform}" for platform in PACKAGE_PLATFORMS]
    return [
        source_root,
        source_root.parent / f"Synapse {version} Linux",
    ]


def copy_shared_contents(source_root: Path, package_root: Path) -> None:
    for filename in ROOT_FILES:
        source = source_root / filename
        if source.exists():
            shutil.copy2(source, package_root / filename)

    for dirname in ROOT_DIRS:
        source = source_root / dirname
        if source.exists():
            shutil.copytree(source, package_root / dirname, ignore=copy_ignore)


def clean_generated_artifacts(package_root: Path) -> None:
    for name in EXCLUDED_NAMES:
        path = package_root / name
        if path.exists():
            if path.is_dir():
                remove_tree(path)
            else:
                path.unlink()

    for name in EXCLUDED_NAMES:
        for path in sorted(package_root.rglob(name), reverse=True):
            if not path.exists():
                continue
            if path.is_dir():
                remove_tree(path)
            else:
                path.unlink()

    for cache_dir in sorted(package_root.rglob("__pycache__"), reverse=True):
        remove_tree(cache_dir)

    for suffix in EXCLUDED_SUFFIXES:
        for path in package_root.rglob(f"*{suffix}"):
            path.unlink()


def copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        path = Path(directory) / name
        if should_exclude(path):
            ignored.add(name)
    return ignored


def should_exclude(path: Path) -> bool:
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def remove_tree(path: Path) -> None:
    make_writable(path)
    shutil.rmtree(path, onerror=handle_remove_error)


def make_writable(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
    except OSError:
        pass

    if not path.is_dir():
        return

    for child in path.rglob("*"):
        try:
            os.chmod(child, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        except OSError:
            pass


def handle_remove_error(function, failed_path, _exc_info) -> None:
    try:
        os.chmod(failed_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        function(failed_path)
    except OSError:
        raise


def write_platform_readme(package_root: Path, platform: str) -> None:
    readme = package_root / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    for name in PACKAGE_PLATFORMS:
        text = text.replace(f"Welcome to the {name} version of Synapse!\n\n", "")
        text = text.replace(f"Welcome to the {name} version of Synapse!\r\n\r\n", "")
    welcome = f"Welcome to the {platform} version of Synapse!"
    if "# Synapse\r\n\r\n" in text:
        text = text.replace("# Synapse\r\n\r\n", f"# Synapse\r\n\r\n{welcome}\r\n\r\n", 1)
    elif "# Synapse\n\n" in text:
        text = text.replace("# Synapse\n\n", f"# Synapse\n\n{welcome}\n\n", 1)
    else:
        text = f"{welcome}\n\n{text}"
    readme.write_text(text, encoding="utf-8")

def write_platform_helpers(package_root: Path, platform: str) -> None:
    if platform == "Windows":
        write_text(
            package_root / "WINDOWS_README.md",
            """# Synapse Windows Package

This package contains the shared Synapse Python source plus Windows-friendly helper scripts.

Quick start:

```powershell
py -m pip install -r requirements.txt
run_synapse.bat
```

Start the local API manually, if you do not want the terminal UI to auto-start it:

```powershell
run_api.bat
```

Run tests:

```powershell
run_tests.bat
```

Run the Ink terminal UI:

```powershell
npm.cmd start
```

The terminal UI auto-starts the default local API in the background when needed and uses stable polling by default. Use `npm.cmd start -- --no-auto-api` if you already started the API yourself, or `npm.cmd start -- --live-events` to try experimental live bullets.

In another terminal:

```powershell
run_tui.bat
```

You can also run the UI smoke check from this folder:

```powershell
npm.cmd start -- --smoke
```

Add the package launcher to your user PATH so the terminal UI can be started as `synapse` or `synapse-tui` from any terminal:

```powershell
add_synapse_to_path.bat
```

After opening a new terminal:

```powershell
synapse
```

Ollama must be installed and running separately. Pull the configured models before normal use.
""",
        )
        write_text(package_root / "run_synapse.bat", "@echo off\r\npy synapse.py %*\r\n")
        write_text(package_root / "run_api.bat", "@echo off\r\npy synapse.py --api %*\r\n")
        write_text(package_root / "install_tui.bat", "@echo off\r\ncd /d %~dp0terminal-ui\r\nnpm.cmd install\r\n")
        write_windows_command_launchers(package_root)
        write_windows_path_installer(package_root)
        write_text(package_root / "install_tui_command.bat", "@echo off\r\ncall \"%~dp0add_synapse_to_path.bat\"\r\n")
        write_text(package_root / "run_tui.bat", "@echo off\r\ncd /d %~dp0terminal-ui\r\nnpm.cmd start -- %*\r\n")
        write_text(package_root / "run_tests.bat", "@echo off\r\npy -m pytest\r\n")
        return

    if platform == "Linux":
        write_text(
            package_root / "LINUX_README.md",
            """# Synapse Linux Package

This package contains the shared Synapse Python source plus Linux-friendly helper scripts.

Quick start:

```sh
python3 -m pip install -r requirements.txt
./run_synapse.sh
```

Start the local API manually, if you do not want the terminal UI to auto-start it:

```sh
./run_api.sh
```

Run tests:

```sh
./run_tests.sh
```

Run the Ink terminal UI:

```sh
npm start
```

The terminal UI auto-starts the default local API in the background when needed and uses stable polling by default. Use `npm start -- --no-auto-api` if you already started the API yourself, or `npm start -- --live-events` to try experimental live bullets.

In another terminal:

```sh
./run_tui.sh
```

You can also run the UI smoke check from this folder:

```sh
npm start -- --smoke
```

Add the package launcher to your PATH so the terminal UI can be started as `synapse` or `synapse-tui` from any terminal:

```sh
./add_synapse_to_path.sh
```

After opening a new terminal:

```sh
synapse
```

Ollama must be installed and running separately. Pull the configured models before normal use.
""",
        )
        write_executable(package_root / "run_synapse.sh", "#!/bin/sh\npython3 synapse.py \"$@\"\n")
        write_executable(package_root / "run_api.sh", "#!/bin/sh\npython3 synapse.py --api \"$@\"\n")
        write_executable(package_root / "install_tui.sh", "#!/bin/sh\ncd \"$(dirname \"$0\")/terminal-ui\" || exit 1\nnpm install\n")
        write_linux_command_launchers(package_root)
        write_linux_path_installer(package_root)
        write_executable(package_root / "install_tui_command.sh", "#!/bin/sh\nexec \"$(dirname \"$0\")/add_synapse_to_path.sh\" \"$@\"\n")
        write_executable(package_root / "run_tui.sh", "#!/bin/sh\ncd \"$(dirname \"$0\")/terminal-ui\" || exit 1\nnpm start -- \"$@\"\n")
        write_executable(package_root / "run_tests.sh", "#!/bin/sh\npython3 -m pytest\n")
        return

    raise ValueError(f"Unsupported platform: {platform}")


def write_windows_command_launchers(package_root: Path) -> None:
    bin_dir = package_root / "bin"
    bin_dir.mkdir(exist_ok=True)
    launcher = (
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"ROOT=%~dp0..\"\r\n"
        "set \"CLI=%ROOT%\\terminal-ui\\source\\cli.js\"\r\n"
        "if /I \"%~1\"==\"--where\" (\r\n"
        "  echo Synapse command: %~f0\r\n"
        "  echo Synapse root: %ROOT%\r\n"
        "  echo Synapse CLI: %CLI%\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "cd /d \"%ROOT%\"\r\n"
        "node \"%CLI%\" %*\r\n"
        "endlocal\r\n"
    )
    write_text(bin_dir / "synapse.cmd", launcher)
    write_text(bin_dir / "synapse-tui.cmd", launcher)

def write_windows_path_installer(package_root: Path) -> None:
    installer = (
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"ROOT=%~dp0\"\r\n"
        "set \"BIN=%ROOT%bin\"\r\n"
        "set \"DRY_RUN=\"\r\n"
        "if /I \"%~1\"==\"--dry-run\" set \"DRY_RUN=1\"\r\n"
        "\r\n"
        "where node.exe >nul 2>nul\r\n"
        "if errorlevel 1 (\r\n"
        "  echo node.exe was not found. Install Node.js first, then run this again.\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        "\r\n"
        "if not exist \"%BIN%\" mkdir \"%BIN%\"\r\n"
        "\r\n"
        "> \"%BIN%\\synapse.cmd\" echo @echo off\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo setlocal\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo set \"ROOT=%%~dp0..\"\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo set \"CLI=%%ROOT%%\\terminal-ui\\source\\cli.js\"\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo if /I \"%%~1\"==\"--where\" ^(\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo   echo Synapse command: %%~f0\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo   echo Synapse root: %%ROOT%%\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo   echo Synapse CLI: %%CLI%%\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo   exit /b 0\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo ^)\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo cd /d \"%%ROOT%%\"\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo node \"%%CLI%%\" %%*\r\n"
        ">> \"%BIN%\\synapse.cmd\" echo endlocal\r\n"
        "\r\n"
        "copy /Y \"%BIN%\\synapse.cmd\" \"%BIN%\\synapse-tui.cmd\" >nul\r\n"
        "\r\n"
        "if defined DRY_RUN (\r\n"
        "  echo Dry run: would place this folder first on your user PATH and remove stale Synapse package bin paths:\r\n"
        "  echo   %BIN%\r\n"
        "  echo No PATH changes were made.\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "\r\n"
        "set \"SYNAPSE_BIN=%BIN%\"\r\n"
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \"$bin=(Resolve-Path -LiteralPath $env:SYNAPSE_BIN).Path.TrimEnd('\\'); $userPath=[Environment]::GetEnvironmentVariable('Path','User'); $items=if ([string]::IsNullOrWhiteSpace($userPath)) { @() } else { @($userPath -split ';' | Where-Object { $_ }) }; $filtered=@(); foreach ($item in $items) { $trim=$item.Trim().TrimEnd('\\'); $lower=$trim.ToLowerInvariant(); if (($lower -like '*\\synapse 0.3 staging\\synapse 0.3.0 windows\\bin') -or ($lower -like '*\\synapse 0.3.0 windows\\bin')) { continue }; if ($filtered -notcontains $trim) { $filtered += $trim } }; $new=@($bin) + @($filtered | Where-Object { $_ -ne $bin }); [Environment]::SetEnvironmentVariable('Path', ($new -join ';'), 'User'); Write-Host 'Placed first on user PATH:' $bin\"\r\n"
        "if errorlevel 1 exit /b 1\r\n"
        "\r\n"
        "echo.\r\n"
        "echo Synapse terminal commands are ready:\r\n"
        "echo   synapse\r\n"
        "echo   synapse-tui\r\n"
        "echo.\r\n"
        "echo Open a new terminal before using them.\r\n"
        "echo Check the active launcher with: synapse --where\r\n"
        "endlocal\r\n"
    )
    write_text(package_root / "add_synapse_to_path.bat", installer)

def write_linux_command_launchers(package_root: Path) -> None:
    bin_dir = package_root / "bin"
    bin_dir.mkdir(exist_ok=True)
    launcher = (
        "#!/bin/sh\n"
        "ROOT=$(CDPATH= cd -- \"$(dirname -- \"$0\")/..\" && pwd)\n"
        "cd \"$ROOT\" || exit 1\n"
        "npm start -- \"$@\"\n"
    )
    write_executable(bin_dir / "synapse", launcher)
    write_executable(bin_dir / "synapse-tui", launcher)


def write_linux_path_installer(package_root: Path) -> None:
    write_executable(
        package_root / "add_synapse_to_path.sh",
        "#!/bin/sh\n"
        "set -eu\n"
        "ROOT=$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\n"
        "BIN=\"$ROOT/bin\"\n"
        "mkdir -p \"$BIN\"\n"
        "cat > \"$BIN/synapse\" <<'EOF'\n"
        "#!/bin/sh\n"
        "ROOT=$(CDPATH= cd -- \"$(dirname -- \"$0\")/..\" && pwd)\n"
        "cd \"$ROOT\" || exit 1\n"
        "npm start -- \"$@\"\n"
        "EOF\n"
        "chmod +x \"$BIN/synapse\"\n"
        "cp \"$BIN/synapse\" \"$BIN/synapse-tui\"\n"
        "chmod +x \"$BIN/synapse-tui\"\n"
        "PROFILE=\"$HOME/.profile\"\n"
        "if [ ! -f \"$PROFILE\" ]; then touch \"$PROFILE\"; fi\n"
        "if ! grep -F \"$BIN\" \"$PROFILE\" >/dev/null 2>&1; then\n"
        "  printf '\\n# Synapse terminal UI\\nexport PATH=\"%s:$PATH\"\\n' \"$BIN\" >> \"$PROFILE\"\n"
        "  printf 'Added to %s: %s\\n' \"$PROFILE\" \"$BIN\"\n"
        "else\n"
        "  printf 'Already present in %s: %s\\n' \"$PROFILE\" \"$BIN\"\n"
        "fi\n"
        "printf '\\nSynapse terminal commands are ready:\\n  synapse\\n  synapse-tui\\n\\n'\n"
        "printf 'Open a new terminal before using them. Start the API with ./run_api.sh, then run synapse from anywhere.\\n'\n",
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def write_executable(path: Path, text: str) -> None:
    write_text(path, text)
    current_mode = path.stat().st_mode
    path.chmod(current_mode | 0o755)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clean platform-specific Synapse release folders.")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional archive output root. Defaults to current Windows folder plus sibling Linux folder.",
    )
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    packages = build_packages(args.source_root, args.output_dir, args.version, args.dry_run)
    for package in packages:
        print(package)


if __name__ == "__main__":
    main()


