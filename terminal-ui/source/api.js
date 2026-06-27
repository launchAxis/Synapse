const DEFAULT_API_URL = 'http://127.0.0.1:8765';
const MAX_SSE_BUFFER_LENGTH = 1024 * 1024;

export function apiBaseUrl() {
  return process.env.SYNAPSE_API_URL || DEFAULT_API_URL;
}

export async function getHealth() {
  return requestJson('/health');
}

export async function getModels() {
  return requestJson('/models');
}

export async function runSynapse({prompt, mode}) {
  return requestJson('/run', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      mode,
      generations: null,
      survivors: null
    })
  });
}

export async function startSynapseRun({prompt, mode, modelPreset}) {
  return requestJson('/runs', {
    method: 'POST',
    body: JSON.stringify({
      prompt,
      mode,
      model_preset: modelPreset || 'local',
      generations: null,
      survivors: null
    })
  });
}

export async function getRunStatus(runId) {
  return requestJson(`/runs/${runId}`);
}
export async function pollRunUntilComplete(runId, onStatus, options = {}) {
  const intervalMs = Number.isFinite(options.intervalMs) ? options.intervalMs : 2000;
  const maxPolls = Number.isFinite(options.maxPolls) ? options.maxPolls : 0;
  let polls = 0;
  while (true) {
    const status = await getRunStatus(runId);
    onStatus?.(status);
    if (status.status === 'complete' || status.status === 'error') {
      return status;
    }
    polls += 1;
    if (maxPolls > 0 && polls >= maxPolls) {
      throw new Error('Synapse run polling exceeded the safe poll limit.');
    }
    await delay(intervalMs);
  }
}

export async function streamRunEvents(eventsUrl, onEvent, onDone) {
  const response = await fetch(`${apiBaseUrl()}${eventsUrl}`, {
    headers: {
      accept: 'text/event-stream'
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Synapse API returned HTTP ${response.status}`);
  }
  const decoder = new TextDecoder();
  let buffer = '';
  for await (const chunk of response.body) {
    buffer += decoder.decode(chunk, {stream: true});
    if (buffer.length > MAX_SSE_BUFFER_LENGTH) {
      throw new Error('Synapse API event stream exceeded the safe buffer size.');
    }
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const parsed = parseSseBlock(part);
      if (!parsed) {
        continue;
      }
      if (parsed.event === 'done') {
        onDone?.(parsed.data);
      } else if (parsed.event === 'event') {
        onEvent?.(parsed.data);
      }
    }
  }
  const tail = parseSseBlock(buffer);
  if (tail?.event === 'done') {
    onDone?.(tail.data);
  } else if (tail?.event === 'event') {
    onEvent?.(tail.data);
  }
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, Math.max(0, ms)));
}

export function parseSseBlock(block) {
  const lines = String(block || '').split(/\r?\n/);
  let event = 'message';
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith(':')) {
      continue;
    }
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim();
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  return {
    event,
    data: JSON.parse(dataLines.join('\n'))
  };
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: {
      'content-type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Synapse API returned HTTP ${response.status}`);
  }
  return payload;
}


