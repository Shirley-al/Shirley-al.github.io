"""Deploy dist/ to GitHub Pages via REST API (bypasses flaky github.com git endpoint)."""
import base64, os, subprocess, sys, time
import urllib.request, json

DIST = os.path.dirname(os.path.abspath(__file__))
REPO = 'Shirley-al/Shirley-al.github.io'

# 1. 从 git 凭据管理器取 token（不打印）
p = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                   capture_output=True, text=True)
token = next(l.split('=', 1)[1] for l in p.stdout.splitlines() if l.startswith('password='))

def api(method, path, payload=None, tries=4):
    url = f'https://api.github.com/repos/{REPO}{path}'
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/vnd.github+json',
                'Content-Type': 'application/json',
                'User-Agent': 'pages-deploy'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f'  [{method} {path}] attempt {attempt+1} failed: {e}', flush=True)
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))

# 2. 收集 dist 下所有文件（排除 .git）
files = []
for root, dirs, names in os.walk(DIST):
    if '.git' in root.split(os.sep):
        continue
    dirs[:] = [d for d in dirs if d != '.git']
    for n in names:
        full = os.path.join(root, n)
        rel = os.path.relpath(full, DIST).replace(os.sep, '/')
        files.append((rel, full))
print(f'{len(files)} files to upload')

# 3. 逐个建 blob
tree = []
for rel, full in files:
    raw = open(full, 'rb').read()
    blob = api('POST', '/git/blobs', {'content': base64.b64encode(raw).decode(), 'encoding': 'base64'})
    tree.append({'path': rel, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    print(f'  blob ok: {rel} ({len(raw)} B)', flush=True)

# 4. 建 tree -> commit -> 更新 main
ref = api('GET', '/git/ref/heads/main')
parent = ref['object']['sha']
t = api('POST', '/git/trees', {'tree': tree})
commit = api('POST', '/git/commits', {
    'message': 'Full-detail 3D antenna showcase (deployed via API)',
    'tree': t['sha'], 'parents': [parent]})
api('PATCH', '/git/refs/heads/main', {'sha': commit['sha']})
print('DEPLOYED:', commit['sha'][:8])
