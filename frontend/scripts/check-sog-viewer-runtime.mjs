import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const viewerPath = resolve('public/sog-viewer/index.js');
const source = readFileSync(viewerPath, 'utf8');

const expectations = [
  {
    name: 'annotation nav updates when runtime annotations are replaced',
    pass: source.includes("events.on('annotations.replaced'"),
  },
  {
    name: 'runtime annotation updates reuse existing entities',
    pass: source.includes('getOrCreateEntity(index)'),
  },
  {
    name: 'runtime annotation updates hide stale entities instead of destroying all entities',
    pass: source.includes('deactivateEntity(entity)') && !source.includes('destroyAnnotationEntities()'),
  },
];

const failed = expectations.filter((item) => !item.pass);

if (failed.length > 0) {
  console.error('SOG viewer runtime checks failed:');
  for (const item of failed) {
    console.error(`- ${item.name}`);
  }
  process.exit(1);
}

console.log(`SOG viewer runtime checks passed (${expectations.length}/${expectations.length}).`);
