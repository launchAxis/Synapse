#!/usr/bin/env node
import {existsSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn, spawnSync} from 'node:child_process';

const sourceDir = dirname(fileURLToPath(import.meta.url));
const terminalUiDir = dirname(sourceDir);
const rootDir = dirname(terminalUiDir);
const inkPackage = join(terminalUiDir, 'node_modules', 'ink', 'package.json');
const defaultApiUrl = 'http://127.0.0.1:8765';
const launchArgs = process.argv.slice(2);

if (!existsSync(inkPackage)) {
  const npmCommand = process.platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : 'npm';
  const npmArgs = process.platform === 'win32' ? ['/d', '/s', '/c', 'npm.cmd install'] : ['install'];
  console.log('Installing Synapse terminal UI dependencies...');
  const result = spawnSync(npmCommand, npmArgs, {
    cwd: terminalUiDir,
    stdio: 'inherit',
    shell: false
  });

  if (result.error) {
    console.error(`Could not start npm install: ${result.error.message}`);
    console.error('Run this once from the Synapse package root instead: npm.cmd --prefix terminal-ui install');
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

if (shouldAutoStartApi()) {
  await ensureLocalApi();
}

await import('./app.js');

function shouldAutoStartApi() {
  return (
    !launchArgs.includes('--smoke') &&
    !launchArgs.includes('--no-auto-api') &&
    !process.env.SYNAPSE_NO_AUTO_API
  );
}

async function ensureLocalApi() {
  const apiUrl = process.env.SYNAPSE_API_URL || defaultApiUrl;
  if (apiUrl !== defaultApiUrl) {
    console.log(`Using configured API URL: ${apiUrl}`);
    return;
  }

  if (await apiHealthy(apiUrl)) {
    return;
  }

  console.log('Starting local Synapse API...');
  const started = startApiTerminal();
  if (started === 'background') {
    console.log('API started in the background.');
  } else {
    console.log('Could not start the API automatically. Start it with run_api.bat, then run synapse again.');
    return;
  }

  const ready = await waitForApi(apiUrl, 15000);
  if (!ready) {
    console.log('API is still warming up. The UI will keep checking the local API.');
  }
}

async function apiHealthy(apiUrl) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 800);
  try {
    const response = await fetch(`${apiUrl}/health`, {signal: controller.signal});
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForApi(apiUrl, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await apiHealthy(apiUrl)) {
      return true;
    }
    await delay(500);
  }
  return false;
}

function delay(ms) {
  return new Promise(resolve => {
    setTimeout(resolve, ms);
  });
}

function startApiTerminal() {
  if (startBackgroundApi()) {
    return 'background';
  }
  return 'failed';
}

function startBackgroundApi() {
  const python = process.platform === 'win32' ? 'py' : 'python3';
  const child = spawn(python, ['synapse.py', '--api'], {
    cwd: rootDir,
    detached: true,
    stdio: 'ignore'
  });
  child.unref();
  return true;
}

