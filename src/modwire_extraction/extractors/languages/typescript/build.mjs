import ncc from '@vercel/ncc';
import { chmod, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = dirname(fileURLToPath(import.meta.url));
const entrypoint = join(projectRoot, 'script.ts');
const output = join(projectRoot, 'script.js');
const cacheDir = join(projectRoot, '.ncc');

await rm(cacheDir, { recursive: true, force: true });

const { code, assets } = await ncc(entrypoint, {
  cache: false,
  minify: false,
  quiet: true,
  sourceMap: false,
  target: 'es2022',
});

const assetNames = Object.keys(assets);
if (assetNames.length > 0) {
  throw new Error(`NCC emitted unsupported sidecar assets: ${assetNames.join(', ')}`);
}

const bundledCode = (code.startsWith('#!') ? code : `#!/usr/bin/env node\n${code}`)
  .replace(/\r\n/g, '\n');
await writeFile(output, bundledCode);
await chmod(output, 0o755);
