export function summarizeModels(models) {
  const usable = Object.keys(models?.usable_models || {}).length;
  const missing = Object.keys(models?.missing_models || {}).length;
  return `${usable} usable local model${usable === 1 ? '' : 's'}, ${missing} missing`;
}

export function summarizePrompt(prompt, limit = 78) {
  const clean = String(prompt || '').replace(/\s+/g, ' ').trim();
  if (clean.length <= limit) {
    return clean;
  }
  return `${clean.slice(0, Math.max(0, limit - 3)).trim()}...`;
}

export function tournamentEvidence(result) {
  const comparisons = [];
  for (const generation of result?.generations || []) {
    comparisons.push(...(generation.comparisons || []));
  }
  return {
    stable: comparisons.filter(item => item.valid && item.stable).length,
    unstable: comparisons.filter(item => item.valid && !item.stable).length,
    invalid: comparisons.filter(item => !item.valid).length
  };
}

export function comparisonLines(result, limit = 8) {
  const comparisons = [];
  for (const generation of result?.generations || []) {
    comparisons.push(...(generation.comparisons || []));
  }
  return comparisons.slice(0, limit).map(item => {
    if (!item.valid) {
      return `${item.idea_a_id} x ${item.idea_b_id}   invalid`;
    }
    if (!item.stable) {
      return `${item.idea_a_id} ? ${item.idea_b_id}   unstable   no win awarded`;
    }
    return `${item.winner_id} > ${item.loser_id}   stable`;
  });
}

export function providerSummary(models) {
  const providers = models?.providers || {};
  const configured = Object.entries(providers)
    .filter(([, value]) => Boolean(value?.configured))
    .map(([name]) => name);
  if (configured.length === 0) {
    return 'providers: ollama local-first';
  }
  return `providers: ${configured.slice(0, 5).join(', ')}${configured.length > 5 ? ', ...' : ''}`;
}

export function eventBullet(event, view = 'council') {
  const bullet = '\u2022';
  const phase = String(event?.phase || 'EVENT').toLowerCase();
  const generation = event?.generation === null || event?.generation === undefined ? '' : ` generation ${event.generation}`;
  const message = compactText(event?.message, 140);
  if (view === 'calm') {
    return `${bullet} ${phase}${generation}`;
  }
  if (view === 'dev') {
    const elapsed = Number.isFinite(event?.elapsed_s) ? ` ${event.elapsed_s}s` : '';
    const model = event?.model ? ` ${event.model}` : '';
    return `${bullet} ${phase}${generation}${model}${elapsed}  ${message}`;
  }
  return `${bullet} ${phase}${generation}  ${message}`;
}

export function selectableEventLine(event, view = 'council', selected = false) {
  return `${selected ? '\u203a' : ' '} ${eventBullet(event, view)}`;
}

export function eventDetailLines(event) {
  if (!event) {
    return [];
  }

  const lines = [];
  if (event.index !== null && event.index !== undefined) {
    lines.push(`index: ${event.index}`);
  }
  if (event.phase) {
    lines.push(`phase: ${event.phase}`);
  }
  if (event.generation !== null && event.generation !== undefined) {
    lines.push(`generation: ${event.generation}`);
  }
  if (event.model) {
    lines.push(`model: ${event.model}`);
  }
  if (Number.isFinite(event.elapsed_s)) {
    lines.push(`elapsed: ${event.elapsed_s}s`);
  }
  if (event.message) {
    lines.push(`message: ${compactText(event.message, 220)}`);
  }
  return lines;
}

export function visibleEvents(events, view = 'council', details = false) {
  const source = Array.isArray(events) ? events : [];
  const fullTraceLimit = 18;
  if (details || view === 'dev') {
    return source.slice(-fullTraceLimit);
  }
  const filtered = view === 'calm'
    ? source.filter(event => !String(event?.message || '').toLowerCase().startsWith('weakness:'))
    : source;
  return filtered.slice(-10);
}
function compactText(value, limit) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(0, limit - 3)).trim()}...`;
}

export function commandList() {
  return [
    ['/help', 'show this list'],
    ['/mode', 'change quick / balanced / deep'],
    ['/view', 'change calm / council / dev detail'],
    ['/preset', 'change local / hybrid / strong intelligence'],
    ['/models', 'refresh model status'],
    ['/providers', 'show provider availability'],
    ['/details', 'toggle recent trace history'],
    ['/clear', 'clear command messages'],
    ['/quit', 'quit the terminal UI']
  ];
}

export function finalWinner(result) {
  const generations = result?.generations || [];
  const last = generations[generations.length - 1];
  return last?.ranked?.[0]?.id || 'not recorded';
}

export function verificationSummary(result) {
  const winner = finalWinner(result);
  const verifications = result?.verifications || [];
  const match = verifications.find(item => item.target_idea_id === winner) || verifications[0];
  if (!match) {
    return 'not recorded';
  }
  const note = match.required_fixes || match.reasoning || '';
  return note ? `${match.verdict}: ${note}` : match.verdict;
}


