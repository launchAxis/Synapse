# Synapse Windows Package

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
