import assert from 'node:assert/strict';
import {parseSseBlock, pollRunUntilComplete} from './api.js';

assert.deepEqual(
  parseSseBlock('event: event\ndata: {"phase":"CONFIG","message":"ready"}'),
  {event: 'event', data: {phase: 'CONFIG', message: 'ready'}}
);

assert.deepEqual(
  parseSseBlock(': keep-alive\n\nevent: done\ndata: {"status":"complete"}'),
  {event: 'done', data: {status: 'complete'}}
);

assert.equal(parseSseBlock(': keep-alive'), null);

const originalFetch = globalThis.fetch;
const statuses = [
  {status: 'running', event_count: 1},
  {status: 'complete', event_count: 2, result: {final_answer: 'ok'}}
];
const seenStatuses = [];
globalThis.fetch = async () => ({
  ok: true,
  json: async () => statuses.shift()
});
const finalStatus = await pollRunUntilComplete('run-test', status => {
  seenStatuses.push(status.status);
}, {intervalMs: 0});
assert.equal(finalStatus.status, 'complete');
assert.deepEqual(seenStatuses, ['running', 'complete']);
globalThis.fetch = originalFetch;