#!/usr/bin/env node
import React, {useEffect, useState} from 'react';
import {Box, Newline, render, Static, Text, useApp, useInput} from 'ink';
import TextInput from 'ink-text-input';
import SelectInput from 'ink-select-input';
import {apiBaseUrl, getHealth, getModels, getRunStatus, pollRunUntilComplete, startSynapseRun, streamRunEvents} from './api.js';
import {
  commandList,
  comparisonLines,
  eventBullet,
  eventDetailLines,
  finalWinner,
  providerSummary,
  selectableEventLine,
  summarizeModels,
  summarizePrompt,
  tournamentEvidence,
  verificationSummary,
  visibleEvents
} from './format.js';
import {renderSignalRingRows} from './signal-ring.js';

const h = React.createElement;
const mark = '\u273b';
const bullet = '\u2022';
const divider = '-'.repeat(42);
const noColor = process.argv.includes('--no-color') || Boolean(process.env.NO_COLOR);
const liveEvents = process.argv.includes('--live-events') || Boolean(process.env.SYNAPSE_LIVE_EVENTS);
const accentBlue = '#2f8cff';
const cyan = '#20b7f0';
const green = '#4ade80';
const amber = '#f5b84b';
const maxStoredRunEvents = 48;
const maxEventTextLength = 180;
const maxStoredFinalAnswerLength = 2400;

const modes = [
  {label: 'quick', value: 'quick'},
  {label: 'balanced', value: 'balanced'},
  {label: 'deep', value: 'deep'}
];

const presets = [
  {label: 'local', value: 'local'},
  {label: 'hybrid', value: 'hybrid'},
  {label: 'strong', value: 'strong'}
];

const views = [
  {label: 'calm', value: 'calm'},
  {label: 'council', value: 'council'},
  {label: 'dev', value: 'dev'}
];

const actions = [
  {label: 'run again', value: 'again'},
  {label: 'change mode', value: 'mode'},
  {label: 'change intelligence', value: 'preset'},
  {label: 'quit', value: 'quit'}
];

function App() {
  const {exit} = useApp();
  const [screen, setScreen] = useState('loading');
  const [health, setHealth] = useState(null);
  const [models, setModels] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState('balanced');
  const [view, setView] = useState('council');
  const [modelPreset, setModelPreset] = useState('local');
  const [details, setDetails] = useState(false);
  const [runEvents, setRunEvents] = useState([]);
  const [runMeta, setRunMeta] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [showHelp, setShowHelp] = useState(false);
  const [commandMessage, setCommandMessage] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [healthPayload, modelPayload] = await Promise.all([getHealth(), getModels()]);
        setHealth(healthPayload);
        setModels(modelPayload);
        setScreen('prompt');
      } catch (err) {
        setError(apiError(err));
        setScreen('api-error');
      }
    }
    load();
  }, []);

  async function submitRun(value = prompt) {
    const cleanPrompt = value.trim();
    if (!cleanPrompt) {
      return;
    }
    setPrompt(cleanPrompt);
    setError('');
    setResult(null);
    setRunEvents([]);
    setRunMeta(null);
    setScreen('running');
    try {
      const started = await startSynapseRun({prompt: cleanPrompt, mode, modelPreset});
      setRunMeta(started);
      await streamRunEvents(
        started.events_url,
        event => setRunEvents(previous => appendRunEvent(previous, event)),
        done => setRunMeta(previous => ({...(previous || started), ...done}))
      );
      const status = await getRunStatus(started.run_id);
      if (status.status === 'error') {
        throw new Error(status.error || 'Synapse run failed.');
      }
      setResult(compactResultForUi(status.result));
      setScreen('result');
    } catch (err) {
      setError(apiError(err));
      setScreen('run-error');
    }
  }

  async function refreshModels() {
    try {
      const payload = await getModels();
      setModels(payload);
      setCommandMessage('Model status refreshed.');
    } catch (err) {
      setCommandMessage(`Could not refresh models: ${apiError(err)}`);
    }
  }

  function handlePromptSubmit(value) {
    const text = value.trim();
    if (!text) {
      setScreen('mode');
      return;
    }
    if (handleCommand(text)) {
      return;
    }
    submitRun(text);
  }

  function handleCommand(text) {
    const command = text.toLowerCase();
    if (command === 'help' || command === '/help' || command === '?') {
      setShowHelp(true);
      setCommandMessage('Command list opened.');
      setPrompt('');
      return true;
    }
    if (command === '/mode' || command === 'mode') {
      setPrompt('');
      setScreen('mode');
      return true;
    }
    if (command === '/view' || command === 'view') {
      setPrompt('');
      setScreen('view');
      return true;
    }
    if (command === '/preset' || command === 'preset' || command === '/intelligence') {
      setPrompt('');
      setScreen('preset');
      return true;
    }
    if (command === '/models' || command === 'models') {
      setPrompt('');
      refreshModels();
      return true;
    }
    if (command === '/providers' || command === 'providers') {
      setPrompt('');
      setCommandMessage(providerSummary(models));
      return true;
    }
    if (command === '/details' || command === 'details' || command === 'd') {
      setPrompt('');
      setDetails(value => {
        const next = !value;
        setCommandMessage(`Full trace ${next ? 'shown' : 'hidden'}.`);
        return next;
      });
      return true;
    }
    if (command === '/clear' || command === 'clear') {
      setPrompt('');
      setShowHelp(false);
      setCommandMessage('');
      return true;
    }
    if (command === '/quit' || command === 'quit' || command === '/exit' || command === 'exit') {
      exit();
      return true;
    }
    if (command.startsWith('/')) {
      setCommandMessage(`Unknown command: ${text}. Try /help.`);
      setPrompt('');
      return true;
    }
    return false;
  }

  function handleAction(item) {
    if (item.value === 'quit') {
      exit();
      return;
    }
    if (item.value === 'mode') {
      setScreen('mode');
      return;
    }
    if (item.value === 'preset') {
      setScreen('preset');
      return;
    }
    setPrompt('');
    setResult(null);
    setRunEvents([]);
    setScreen('prompt');
  }

  return h(
    Box,
    {flexDirection: 'column', paddingY: 1},
    screen === 'loading' && h(LoadingScreen),
    screen === 'api-error' && h(ApiError, {message: error}),
    screen === 'prompt' && h(PromptScreen, {
      health,
      mode,
      modelPreset,
      view,
      models,
      onSubmitText: handlePromptSubmit,
      commandMessage,
      showHelp
    }),
    screen === 'mode' && h(ChoiceScreen, {title: 'Select mode', items: modes, value: mode, setValue: setMode, onDone: () => setScreen('prompt')}),
    screen === 'view' && h(ChoiceScreen, {title: 'Select view', items: views, value: view, setValue: setView, onDone: () => setScreen('prompt')}),
    screen === 'preset' && h(ChoiceScreen, {title: 'Select intelligence', items: presets, value: modelPreset, setValue: setModelPreset, onDone: () => setScreen('prompt')}),
    screen === 'running' && h(RunScreen, {prompt, mode, modelPreset, view, details, runEvents, runMeta, setDetails, liveEvents}),
    screen === 'run-error' && h(RunError, {message: error, onRetry: () => setScreen('prompt')}),
    screen === 'result' && h(ResultScreen, {result, details, setDetails, onAction: handleAction})
  );
}

const StartupFrame = React.memo(function StartupFrame({health, models, mode, modelPreset, view, status}) {
  const version = health?.version ? `v${health.version}` : 'local API';
  return h(
    Box,
    {
      borderStyle: 'round',
      borderColor: color(accentBlue),
      flexDirection: 'column',
      paddingX: 1,
      paddingY: 1
    },
    h(
      Box,
      {flexDirection: 'row', gap: 2},
      h(
        Box,
        {flexDirection: 'column', width: 32, alignItems: 'center'},
        h(Text, {dimColor: true}, 'Welcome back'),
        h(Box, {marginY: 1}, h(SignalRingLogo)),
        h(Text, null, h(Text, {color: color(accentBlue)}, mark), ' ', h(Text, {bold: true}, 'Synapse'), ' ', h(Text, {dimColor: true}, version)),
        h(Text, {dimColor: true}, 'local-first idea evolution'),
        h(Newline),
        h(Text, {dimColor: true}, summarizeModels(models)),
        h(Text, {dimColor: true}, `mode ${mode}`),
        h(Text, {dimColor: true}, `intelligence ${modelPreset}`),
        h(Text, {dimColor: true}, `view ${view}`),
        h(Text, {dimColor: true}, `API ${apiBaseUrl()}`),
        h(Text, {dimColor: true}, summarizePrompt(process.cwd(), 32)),
        status && h(Newline),
        status && h(Text, {color: color(cyan)}, status)
      ),
      h(
        Box,
        {flexDirection: 'column', width: 44},
        h(Text, {bold: true}, 'Tips for getting started'),
        h(Text, null, 'Run ', h(Text, {color: color(cyan)}, 'synapse'), ' from any terminal.'),
        h(Text, null, 'Type ', h(Text, {color: color(accentBlue)}, '/help'), ' for commands.'),
        h(Text, null, 'Use ', h(Text, {color: color(accentBlue)}, '/view'), ' for calm/council/dev traces.'),
        h(Text, null, 'Use ', h(Text, {color: color(accentBlue)}, '/preset'), ' for local/hybrid/strong.'),
        h(Text, {dimColor: true}, divider),
        h(Text, {bold: true}, "What's new"),
        h(Text, null, 'Stable run monitor by default.'),
        h(Text, null, 'Use ', h(Text, {color: color(cyan)}, '--live-events'), ' for experimental bullets.'),
        h(Text, null, 'Provider-aware model status.'),
        h(Text, null, 'Blocking /run still works for scripts.')
      )
    )
  );
});

const SignalRingLogo = React.memo(function SignalRingLogo() {
  const rows = renderSignalRingRows({color: !noColor});
  return h(
    Box,
    {flexDirection: 'column', alignItems: 'center'},
    ...rows.map((row, rowIndex) =>
      h(
        Text,
        {key: `ring-row-${rowIndex}`},
        ...row.map((span, columnIndex) =>
          h(
            Text,
            {
              key: `ring-cell-${rowIndex}-${columnIndex}`,
              color: span.fg,
              backgroundColor: span.bg
            },
            span.char
          )
        )
      )
    )
  );
});

function ApiError({message}) {
  return h(
    Box,
    {flexDirection: 'column'},
    h(StartupFrame, {health: null, models: null, mode: 'balanced', modelPreset: 'local', view: 'council'}),
    h(Newline),
    h(Text, {color: 'red'}, 'Could not reach the local Synapse API.'),
    h(Newline),
    h(Text, {dimColor: true}, 'Start it in another terminal:'),
    h(Text, null, '  python synapse.py --api'),
    h(Newline),
    h(Text, {dimColor: true}, 'Then run this UI:'),
    h(Text, null, '  synapse'),
    h(Newline),
    h(Text, {dimColor: true}, `API URL: ${apiBaseUrl()}`),
    h(Text, {dimColor: true}, message)
  );
}

function PromptScreen({health, mode, modelPreset, view, models, onSubmitText, commandMessage, showHelp}) {
  const welcome = {
    id: `welcome-${health?.version || 'api'}-${mode}-${modelPreset}-${view}-${Object.keys(models?.usable_models || {}).length}-${Object.keys(models?.missing_models || {}).length}`,
    health,
    models,
    mode,
    modelPreset,
    view
  };
  return h(
    Box,
    {flexDirection: 'column'},
    h(
      Static,
      {items: [welcome]},
      item => h(StartupFrame, {
        key: item.id,
        health: item.health,
        models: item.models,
        mode: item.mode,
        modelPreset: item.modelPreset,
        view: item.view
      })
    ),
    h(Newline),
    h(Text, {dimColor: true}, 'Prompt  ', h(Text, null, mode), ' ', h(Text, {dimColor: true}, modelPreset), ' ', h(Text, {dimColor: true}, '(try /help)')),
    h(PromptInputLine, {onSubmitText}),
    commandMessage && h(Text, {color: color(cyan)}, commandMessage),
    showHelp && h(CommandHelp)
  );
}

function PromptInputLine({onSubmitText}) {
  const [draft, setDraft] = useState('');
  return h(
    Box,
    null,
    h(Text, {color: color(accentBlue)}, '\u203a '),
    h(TextInput, {
      value: draft,
      onChange: setDraft,
      onSubmit: value => {
        const submitted = value;
        setDraft('');
        onSubmitText(submitted);
      },
      placeholder: 'Describe the problem for the council'
    })
  );
}

function CommandHelp() {
  return h(
    Box,
    {flexDirection: 'column', marginTop: 1},
    h(Text, {bold: true}, 'Commands'),
    ...commandList().map(([command, description]) =>
      h(Text, {key: command}, h(Text, {color: color(accentBlue)}, command.padEnd(10)), description)
    )
  );
}

function LoadingScreen() {
  return h(
    Box,
    {flexDirection: 'column', paddingX: 1},
    h(Text, null, h(Text, {color: color(accentBlue)}, mark), ' ', h(Text, {bold: true}, 'Synapse')),
    h(Text, {dimColor: true}, 'Connecting to local Synapse API...')
  );
}

function ChoiceScreen({title, items, value, setValue, onDone}) {
  return h(
    Box,
    {flexDirection: 'column'},
    h(Text, {dimColor: true}, title),
    h(SelectInput, {
      items: items.map(item => ({...item, label: item.value === value ? `${item.label} current` : item.label})),
      onSelect: item => {
        setValue(item.value);
        onDone();
      }
    })
  );
}

function appendRunEvent(previous, event) {
  const next = [...previous, compactRunEvent(event)];
  if (next.length <= maxStoredRunEvents) {
    return next;
  }
  return next.slice(next.length - maxStoredRunEvents);
}

function compactRunEvent(event) {
  return {
    index: event?.index,
    phase: truncateText(event?.phase, 80),
    generation: event?.generation,
    model: truncateText(event?.model, 160),
    elapsed_s: Number.isFinite(event?.elapsed_s) ? event.elapsed_s : undefined,
    message: truncateText(event?.message, maxEventTextLength)
  };
}

function truncateText(value, limit) {
  if (value === null || value === undefined) {
    return value;
  }
  const text = String(value).replace(/\s+/g, ' ').trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(0, limit - 3)).trim()}...`;
}

function eventIdentity(event, fallbackIndex) {
  if (!event) {
    return '';
  }
  const index = event.index ?? fallbackIndex;
  return `${index}:${event.phase || 'EVENT'}:${event.generation ?? ''}:${event.message || ''}`;
}
function RunScreen(props) {
  return props.liveEvents ? h(LiveRunScreen, props) : h(SafeRunScreen, props);
}

function LiveRunScreen({prompt, mode, modelPreset, view, details, runEvents, runMeta, setDetails}) {
  const visible = visibleEvents(runEvents, view, details);
  const [selectedEventIndex, setSelectedEventIndex] = useState(0);
  const [expandedEventKey, setExpandedEventKey] = useState('');

  useEffect(() => {
    setSelectedEventIndex(value => Math.max(0, Math.min(value, Math.max(0, visible.length - 1))));
  }, [visible.length]);

  const selectedEvent = visible[selectedEventIndex];
  const selectedKey = eventIdentity(selectedEvent, selectedEventIndex);
  const selectedExpanded = selectedKey && expandedEventKey === selectedKey;

  useInput((input, key) => {
    if (input.toLowerCase() === 'd') {
      setDetails(value => !value);
      return;
    }
    if (key.upArrow) {
      setSelectedEventIndex(value => Math.max(0, value - 1));
      return;
    }
    if (key.downArrow) {
      setSelectedEventIndex(value => Math.min(Math.max(0, visible.length - 1), value + 1));
      return;
    }
    if (key.return && selectedEvent) {
      setExpandedEventKey(value => (value === selectedKey ? '' : selectedKey));
    }
  });

  return h(
    Box,
    {flexDirection: 'column'},
    h(Text, null, h(Text, {color: color(accentBlue)}, mark), ' ', h(Text, {bold: true}, 'Synapse')),
    h(Text, {dimColor: true}, `mode ${mode}   intelligence ${modelPreset}   view ${view}${details ? '   full trace' : ''}`),
    h(Newline),
    h(Text, {dimColor: true}, 'Prompt'),
    h(Text, null, summarizePrompt(prompt)),
    h(Newline),
    h(Text, {color: color(cyan)}, runMeta?.run_id ? `Run ${runMeta.run_id}` : 'Preparing council...'),
    visible.length === 0 && h(Text, {color: color(cyan)}, `${bullet} waiting for first core event`),
    ...visible.map((event, index) =>
      h(Text, {key: `${event.index || index}-${event.phase}-${index}`, color: eventColor(event)}, selectableEventLine(event, view, index === selectedEventIndex))
    ),
    selectedExpanded && selectedEvent && h(
      Box,
      {flexDirection: 'column', marginLeft: 4, marginTop: 1},
      ...eventDetailLines(selectedEvent).map(line => h(Text, {key: line, dimColor: true}, line))
    ),
    h(Newline),
    h(Text, {dimColor: true}, `showing ${visible.length}/${runEvents.length} recent events`),
    h(Text, {dimColor: true}, 'Up/Down select. Enter expands selected. d shows recent trace. Full output is in logs.')
  );
}

function SafeRunScreen({prompt, mode, modelPreset, view, runMeta}) {
  const eventCount = Number.isFinite(runMeta?.event_count) ? runMeta.event_count : 0;
  const status = runMeta?.status || 'running';
  const displayStatus = status === 'queued' && eventCount > 0 ? 'running' : status;
  return h(
    Box,
    {flexDirection: 'column'},
    h(Text, null, h(Text, {color: color(accentBlue)}, mark), ' ', h(Text, {bold: true}, 'Synapse')),
    h(Text, {dimColor: true}, `mode ${mode}   intelligence ${modelPreset}   view ${view}   stable monitor`),
    h(Newline),
    h(Text, {dimColor: true}, 'Prompt'),
    h(Text, null, summarizePrompt(prompt)),
    h(Newline),
    h(Text, {color: color(cyan)}, runMeta?.run_id ? `Run ${runMeta.run_id}` : 'Preparing council...'),
    h(Text, {color: color(cyan)}, `${bullet} running Synapse`),
    h(Text, {dimColor: true}, `status ${displayStatus}   core events recorded ${eventCount}`),
    h(Text, {dimColor: true}, 'Final synthesis will appear here when the run completes.'),
    h(Text, {dimColor: true}, 'Experimental live bullets are available with: synapse --live-events')
  );
}
function RunError({message, onRetry}) {
  return h(
    Box,
    {flexDirection: 'column'},
    h(Text, {color: 'red'}, 'Synapse run failed.'),
    h(Text, {dimColor: true}, message),
    h(Newline),
    h(SelectInput, {items: [{label: 'try another prompt', value: 'retry'}], onSelect: onRetry})
  );
}

function ResultScreen({result, details, setDetails, onAction}) {
  useInput(input => {
    if (input.toLowerCase() === 'd') {
      setDetails(value => !value);
    }
  });
  const evidence = tournamentEvidence(result);
  const comparisons = comparisonLines(result, details ? 10 : 4);
  const answer = result?.final_answer || '(empty)';
  const answerPreview = truncateText(answer, details ? 1800 : 900);
  const answerTruncated = Boolean(result?.final_answer_truncated) || String(answer).length > answerPreview.length;
  return h(
    Box,
    {flexDirection: 'column'},
    h(Text, null, h(Text, {color: color(accentBlue)}, mark), ' ', h(Text, {bold: true}, 'Synapse')),
    h(Text, {color: color(green)}, 'Final synthesis ready'),
    h(Newline),
    h(Text, {dimColor: true}, 'Winner'),
    h(Text, null, finalWinner(result)),
    h(Newline),
    h(Text, {dimColor: true}, 'Verification'),
    h(Text, null, truncateText(verificationSummary(result), 500)),
    h(Newline),
    h(Text, {dimColor: true}, 'Tournament evidence'),
    h(Text, null, `stable ${evidence.stable}   unstable ${evidence.unstable}   invalid ${evidence.invalid}`),
    comparisons.length > 0 && h(Box, {flexDirection: 'column', marginTop: 1}, ...comparisons.map((line, index) => h(Text, {key: `${line}-${index}`, dimColor: true}, line))),
    h(Newline),
    h(Text, {dimColor: true}, `Final answer preview${answerTruncated ? ' (truncated)' : ''}`),
    h(Text, null, answerPreview),
    answerTruncated && h(Text, {dimColor: true}, 'Full final answer is saved in the log folder below.'),
    h(Newline),
    h(Text, {dimColor: true}, 'Logs'),
    h(Text, null, result?.run_directory || 'not recorded'),
    h(Newline),
    h(Text, {dimColor: true}, 'Actions   ', h(Text, null, 'd toggles a larger preview')),
    h(SelectInput, {items: actions, onSelect: onAction})
  );
}

function SmokeScreen() {
  return h(
    Box,
    {flexDirection: 'column'},
    h(StartupFrame, {
      health: {version: '0.3.0'},
      mode: 'balanced',
      modelPreset: 'local',
      view: 'council',
      models: {usable_models: {A: 'qwen2.5:3b', B: 'gemma2:2b'}, missing_models: {}}
    }),
    h(Text, {dimColor: true}, 'terminal UI smoke check')
  );
}

function compactResultForUi(result) {
  const finalAnswer = String(result?.final_answer || '');
  return {
    final_answer: truncateText(finalAnswer, maxStoredFinalAnswerLength),
    final_answer_truncated: finalAnswer.length > maxStoredFinalAnswerLength,
    run_directory: result?.run_directory || result?.log_dir || 'not recorded',
    generations: compactGenerations(result?.generations || []),
    verifications: compactVerifications(result?.verifications || [])
  };
}

function compactGenerations(generations) {
  return generations.slice(-3).map(generation => ({
    comparisons: (generation?.comparisons || []).slice(0, 18).map(comparison => ({
      idea_a_id: comparison?.idea_a_id,
      idea_b_id: comparison?.idea_b_id,
      winner_id: comparison?.winner_id,
      loser_id: comparison?.loser_id,
      valid: Boolean(comparison?.valid),
      stable: Boolean(comparison?.stable)
    })),
    ranked: (generation?.ranked || []).slice(0, 3).map(item => ({
      id: item?.id || item?.idea_id || String(item || '')
    }))
  }));
}

function compactVerifications(verifications) {
  return verifications.slice(0, 3).map(item => ({
    target_idea_id: item?.target_idea_id,
    verdict: truncateText(item?.verdict, 80),
    required_fixes: truncateText(item?.required_fixes, 400),
    reasoning: truncateText(item?.reasoning, 400)
  }));
}
function apiError(err) {
  return err instanceof Error ? err.message : String(err);
}

function color(value) {
  return noColor ? undefined : value;
}

function eventColor(event) {
  if (noColor) {
    return undefined;
  }
  const phase = String(event?.phase || '').toUpperCase();
  if (phase === 'ERROR') {
    return 'red';
  }
  if (phase === 'TOURNAMENT') {
    return amber;
  }
  if (phase === 'SYNTHESIS' || phase === 'LOG') {
    return green;
  }
  return cyan;
}

if (process.argv.includes('--smoke')) {
  render(h(SmokeScreen)).unmount();
} else {
  render(h(App));
}

