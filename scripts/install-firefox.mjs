// Keep browser downloads out of shared caches and never trigger global cache GC.
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cache = resolve(root, 'artifacts/browsers');
const env = {
  ...process.env,
  PLAYWRIGHT_BROWSERS_PATH: cache,
  PLAYWRIGHT_SKIP_BROWSER_GC: '1',
};
if (process.argv.includes('--plan')) {
  console.log(JSON.stringify({ browserCache: cache, skipBrowserGC: true, modelInvoked: false }, null, 2));
} else {
  mkdirSync(cache, { recursive: true, mode: 0o700 });
  const result = spawnSync(process.execPath, [resolve(root, 'node_modules/playwright/cli.js'), 'install', 'firefox'], {
    cwd: root,
    env,
    stdio: 'inherit',
  });
  process.exitCode = result.error ? 1 : (result.status ?? 1);
}
