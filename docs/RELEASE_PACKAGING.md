# Release Packaging

Synapse 0.3.0 should ship as separate platform folders while keeping one shared Python codebase. In the staging workspace, the Windows folder is the source-bearing package and the Linux folder is rebuilt beside it:

```text
Synapse 0.3 staging/
  Synapse 0.3.0 Windows/
  Synapse 0.3.0 Linux/
```

Both packages include the same shared source, tests, docs, configs, benchmark suites, and requirements files. Platform differences are limited to small helper launch scripts and platform notes:

- Windows package: `run_synapse.bat`, `run_api.bat`, `run_tui.bat`, `run_tests.bat`, `WINDOWS_README.md`
- Linux package: `run_synapse.sh`, `run_api.sh`, `run_tui.sh`, `run_tests.sh`, `LINUX_README.md`

The packaging script intentionally excludes generated artifacts:

- `logs/`
- `runs/`
- `bench_runs/`
- `.bench_cache/`
- `.pytest_cache/`
- `__pycache__/`
- `*.pyc`
- `dist/`
- `node_modules/`

Build or refresh the sibling Linux package from the source-bearing Windows folder:

```bash
python scripts/build_release_packages.py
```

Preview without writing files:

```bash
python scripts/build_release_packages.py --dry-run
```

The script does not build installers, containers, native packages, or binaries. Docker, `.deb`, AppImage, MSI, and signed installers remain out of scope for this release stage.

For archive-style release assembly later, write both platform folders under a separate output root:

```bash
python scripts/build_release_packages.py --output-dir dist
```
