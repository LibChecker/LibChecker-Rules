import fs from 'node:fs';
import assert from 'node:assert/strict';
const { vectors, fixtures } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function fullMatch(pattern, value) {
  if (/[\n\r\u0085\u2028\u2029]/u.test(value)) return false;
  const match = new RegExp(`^(?:${pattern})$`, 'u').exec(value);
  return match !== null && match[0].length === value.length;
}
for (const [pattern, value, expected] of vectors) assert.equal(fullMatch(pattern, value), expected, `${pattern}: ${value}`);
for (const test of fixtures) {
  const exact = test.rules.find(r => r.type === test.type && r.name === test.input);
  const regex = test.useRegex === false ? null : [...test.rules].sort((a, b) => a.priority - b.priority || a.id - b.id)
    .find(r => r.type === test.type && r.isRegexRule && fullMatch(r.name, test.input));
  assert.equal((exact ?? regex)?.id ?? null, test.expected, test.name);
}
console.log(`JavaScript: ${vectors.length} regex vectors, ${fixtures.length} matching fixtures passed`);
