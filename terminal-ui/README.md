# Synapse Terminal UI

This is the optional Ink/React terminal frontend for Synapse. It calls the local Python API and does not reimplement Synapse logic in Node.

The terminal frontend auto-starts the default local API in the background when needed. Use `--no-auto-api` if you prefer to start the API yourself.

Install and run the terminal UI in another terminal:

```bash
npm install
npm start
```

Use `npm start -- --no-auto-api` if you already started the API yourself or are using `SYNAPSE_API_URL`.

From the release package root, you can also run:

```bash
npm start
npm start -- --smoke
```

On Windows PowerShell, use `npm.cmd` if `npm.ps1` is blocked by execution policy:

```powershell
npm.cmd install
npm.cmd start
```

For a simpler Claude-Code-style command from the Windows package root, run:

```powershell
.\add_synapse_to_path.bat
```

Open a new terminal afterward, then run:

```powershell
synapse
```

The same UI is also available as `synapse-tui` to avoid name conflicts.

The `synapse` command also auto-starts the default local API. Use `synapse --no-auto-api` to skip that behavior. By default the run monitor uses lightweight polling for stability; use `synapse --live-events` to try the experimental Server-Sent Events progress view. If Synapse was moved or renamed, rerun `add_synapse_to_path.bat`, open a new terminal, and check `synapse --where`.

If you prefer npm's own global-link mechanism instead, you can still run this from `terminal-ui/`:

```powershell
npm.cmd install
npm.cmd link
```

The API URL defaults to `http://127.0.0.1:8765`. Override it with:

```bash
set SYNAPSE_API_URL=http://127.0.0.1:8765
```

On Linux/macOS:

```bash
SYNAPSE_API_URL=http://127.0.0.1:8765 npm start
```

## Commands

Type these into the prompt field:

- `/help` shows the command list.
- `/mode` changes quick / balanced / deep mode.
- `/view` changes calm / council / dev detail level.
- `/preset` changes local / hybrid / strong intelligence.
- `/models` refreshes local model status.
- `/providers` shows provider availability.
- `/details` toggles expanded run details.
- `/clear` clears command messages.
- `/quit` exits the terminal UI.

The default run screen uses `POST /runs` plus lightweight polling of `GET /runs/{id}`. This keeps the terminal stable during long Ollama runs while still preserving model presets and final result evidence. Experimental live bullets are still available with `synapse --live-events`; in that mode progress bullets come from real Synapse core events rather than fake phase timers. Use Up/Down to select a live progress bullet, press `Enter` to expand just that bullet, or press `d` to toggle recent trace history. Mouse clicks are not relied on because terminal mouse support varies across Windows Terminal, VS Code, Linux terminals, and SSH.

The welcome screen renders the Synapse Signal Ring with ANSI truecolor half-block pixels. One terminal cell represents two vertical logo pixels, which keeps the ring compact without turning it into a full-block blob. The welcome panel is printed as a static block, and the prompt input keeps its live draft local so typing does not repaint the whole panel. Use `npm start -- --no-color` for a simple text fallback.
