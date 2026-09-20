// Local guard: inspect Git blobs, never print secret values or working .env files.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export function inspect(name, content) {
  const base = name.split('/').at(-1);
  if ((base === '.env' || base.startsWith('.env.')) && !/\.(example|sample)$/.test(base)) return 'private environment file';
  if (/\bsk-[A-Za-z0-9_-]{16,}\b/.test(content)) return 'possible API credential';
  if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(content)) return 'private key';
  if (/\.(example|sample)$/.test(base) && /^(?:DEEPSEEK|DASHSCOPE)_API_KEY[ \t]*=[ \t]*[^\s#"'][^\r\n]*$/m.test(content)) return 'nonempty credential template';
  return null;
}
const git = (...args) => execFileSync('git', args, { maxBuffer: 64 * 1024 * 1024 });
function checkTree(ref, staged = false, changedOnly = false) {
  const args = staged
    ? ['diff','--cached','--name-only','--diff-filter=ACMR','-z']
    : changedOnly
      ? ['diff-tree','--no-commit-id','--name-only','--diff-filter=ACMR','-r','-z',ref]
      : ['ls-tree','-r','--name-only','-z',ref];
  const names = git(...args).toString().split('\0').filter(Boolean);
  let rejected = false;
  for (const name of names) {
    const blob = git('show',`${staged ? '' : ref}:${name}`).toString('utf8');
    const reason = inspect(name,blob);
    if (reason) { console.error(`BLOCKED: ${name} (${reason}). No secret values are displayed.`); rejected = true; }
  }
  return rejected;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    let rejected = false;
    if (process.argv.includes('--push')) {
      const refs = readFileSync(0,'utf8').trim().split('\n').filter(Boolean);
      const commits = new Set();
      for (const line of refs) {
        const [,localSha,,remoteSha] = line.trim().split(/\s+/);
        if (/^0+$/.test(localSha)) continue;
        const args = /^0+$/.test(remoteSha) ? ['rev-list',localSha,'--not','--remotes'] : ['rev-list',`${remoteSha}..${localSha}`];
        for (const sha of git(...args).toString().trim().split('\n').filter(Boolean)) commits.add(sha);
      }
      for (const sha of commits) rejected = checkTree(sha, false, true) || rejected;
    } else rejected = checkTree('HEAD',process.argv.includes('--staged'));
    if(rejected) process.exitCode=1;
    else console.log('Secret guard passed. No credential values displayed.');
  } catch { console.error('Secret guard could not complete. Commit/push blocked; inspect local setup.'); process.exitCode=1; }
}
