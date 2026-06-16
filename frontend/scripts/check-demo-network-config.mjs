import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (path) => readFileSync(join(root, path), 'utf8');
const exists = (path) => existsSync(join(root, path));
const scheduleService = read('frontend/src/features/schedule/services/schedule.ts');

const checks = [
  {
    name: 'frontend agent calls do not fall back to browser localhost',
    ok: !/VITE_AGENT_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:7401['"]/.test(read('frontend/src/hooks/useSduiStream.ts'))
      && !/VITE_AGENT_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:7401['"]/.test(read('frontend/src/hooks/useChatStream.ts'))
      && !/VITE_AGENT_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:7401['"]/.test(read('frontend/src/components/twin/survey-twin/survey-twin-viewer.tsx'))
      && !/VITE_AGENT_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:7401['"]/.test(read('frontend/src/components/screens/preview.tsx'))
      && !/VITE_AGENT_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:7401['"]/.test(read('frontend/src/components/screens/evals/shared.tsx')),
  },
  {
    name: 'ontology calls do not fall back to browser localhost',
    ok: !/VITE_ONTOLOGY_BASE\s*\|\|\s*['"]http:\/\/127\.0\.0\.1:8011['"]/.test(read('frontend/src/lib/ontology-api.ts')),
  },
  {
    name: 'schedule API uses runtime agent base in static demo',
    ok: scheduleService.includes("from '@/lib/runtimeBase'")
      && /agentBase\(\)/.test(scheduleService)
      && !/fetch\(\s*(GENERATE_PATH|ADJUST_PATH|COMMIT_PATH|PARSE_CHANGES_PATH|REPORT_SUMMARY_PATH|EXPORT_PLAN_PATH|PROJECT_DATA_PATH|API_PREFIX)/.test(scheduleService),
  },
  {
    name: 'nginx proxies SOG APIs to agent',
    ok: /location\s+\/api\/sog/.test(read('frontend/nginx.conf'))
      && /location\s+\/data\/sog-assets/.test(read('frontend/nginx.conf')),
  },
  {
    name: 'vite dev proxy includes SOG APIs',
    ok: /['"]\/api\/sog['"]/.test(read('frontend/vite.config.ts'))
      && /['"]\/data\/sog-assets['"]/.test(read('frontend/vite.config.ts')),
  },
  {
    name: 'compose includes mailgw service',
    ok: /(^|\n)\s+mailgw:\s*\n/.test(read('docker-compose.yml')),
  },
  {
    name: 'mailgw image has Dockerfile',
    ok: exists('mailgw/Dockerfile')
      && /python["']?\s*,\s*["']-m["']?\s*,\s*["']mailgw/.test(read('mailgw/Dockerfile')),
  },
  {
    name: 'SOG runtime paths are configurable',
    ok: read('agent/sog_assets.py').includes('AIDA_SOG_DATA_ROOT')
      && read('agent/sog_routes.py').includes('AIDA_SOG_PROBE_EVENTS'),
  },
];

const failed = checks.filter((check) => !check.ok);
for (const check of checks) {
  console.log(`${check.ok ? 'ok' : 'not ok'} - ${check.name}`);
}
if (failed.length) {
  process.exitCode = 1;
}
