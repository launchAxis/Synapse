import assert from 'node:assert/strict';
import {
  commandList,
  comparisonLines,
  eventBullet,
  eventDetailLines,
  providerSummary,
  selectableEventLine,
  visibleEvents
} from './format.js';

assert.equal(
  eventBullet({phase: 'TOURNAMENT', generation: 2, message: 'recorded 1 stable'}, 'council'),
  '\u2022 tournament generation 2  recorded 1 stable'
);

assert.equal(
  eventBullet({phase: 'SYNTHESIS', message: 'done', elapsed_s: 4.2, model: 'openai:gpt-test'}, 'dev'),
  '\u2022 synthesis openai:gpt-test 4.2s  done'
);

assert.equal(
  eventBullet({phase: 'CRITIQUE', generation: 0, message: 'weakness: too broad'}, 'calm'),
  '\u2022 critique generation 0'
);

assert.equal(
  selectableEventLine({phase: 'TOURNAMENT', message: 'round complete'}, 'council', true),
  '\u203a \u2022 tournament  round complete'
);

assert.deepEqual(
  eventDetailLines({index: 3, phase: 'TOURNAMENT', generation: 2, model: 'qwen2.5:3b', elapsed_s: 7.5, message: 'stable 2 unstable 1'}),
  ['index: 3', 'phase: TOURNAMENT', 'generation: 2', 'model: qwen2.5:3b', 'elapsed: 7.5s', 'message: stable 2 unstable 1']
);

const result = {
  generations: [
    {
      comparisons: [
        {idea_a_id: 'I1', idea_b_id: 'I2', winner_id: 'I2', loser_id: 'I1', valid: true, stable: true},
        {idea_a_id: 'I3', idea_b_id: 'I4', valid: true, stable: false},
        {idea_a_id: 'I5', idea_b_id: 'I6', valid: false, stable: false}
      ]
    }
  ]
};

assert.deepEqual(comparisonLines(result), [
  'I2 > I1   stable',
  'I3 ? I4   unstable   no win awarded',
  'I5 x I6   invalid'
]);

assert.equal(
  providerSummary({providers: {ollama: {configured: true}, openai: {configured: true}, google: {configured: false}}}),
  'providers: ollama, openai'
);

assert.ok(commandList().some(([command]) => command === '/details'));
assert.equal(visibleEvents([{message: 'weakness: x'}, {message: 'done'}], 'calm').length, 1);
assert.equal(visibleEvents([{message: 'weakness: x'}], 'dev').length, 1);
assert.equal(visibleEvents(Array.from({length: 100}, (_, index) => ({index})), 'dev').length, 18);
assert.equal(visibleEvents(Array.from({length: 100}, (_, index) => ({index})), 'council', true).length, 18);

