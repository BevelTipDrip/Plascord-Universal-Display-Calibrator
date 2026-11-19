#!/usr/bin/env python3
"""Change map: one card per change in research/changes/, facts computed from git and the code,
lookups that need no reading of the big docs, and a check that keeps the cards and docs true.

  python research/tools/changemap.py check [--list] [area]  recompute facts; validate cards, links, index
  python research/tools/changemap.py index            rebuild research/changes/INDEX.md and TESTS.md
  python research/tools/changemap.py facts            recompute research/changes/_facts/ (git, code, docs)
  python research/tools/changemap.py file <path>      cards touching a file, with their invariants
  python research/tools/changemap.py switch <name>    a switch: its card, default and code sites
  python research/tools/changemap.py commit <hash>    the card a commit belongs to
  python research/tools/changemap.py test <id>        where a test ID is written up
  python research/tools/changemap.py show <id>        print a card
  python research/tools/changemap.py find <text>      search card IDs, titles and bodies
  python research/tools/changemap.py doc <file.md>    a doc's outline with anchors
  python research/tools/changemap.py area <area>      the cards of one area
  python research/tools/changemap.py new <area> <id>  a new card from research/templates/card.md
  python research/tools/changemap.py branches [--no-fetch]  every active branch: owner, goal, overlaps and
                                                      conflicts with yours (reads their reference files from the remote)
  python research/tools/changemap.py new-branch <name>  the reference file research/branches/<name>.md
  python research/tools/changemap.py queue            the work queue's Now and Next, compact, with stale claims
  python research/tools/changemap.py queue <Q-n>      one item and everything that references it
  python research/tools/changemap.py queue next       the next free queue ID

Settings: research/tools/changemap.config.json. Card format: research/changes/README.md. Branch reference
files: research/branches/README.md. Python 3.8+, standard library only.
"""
import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CHANGES = os.path.join(ROOT, 'research', 'changes')
FACTS = os.path.join(CHANGES, '_facts')
DOCS = os.path.join(ROOT, 'research', 'docs')
BRANCH_DOCS = os.path.join(ROOT, 'research', 'branches')
TEMPLATES = os.path.join(ROOT, 'research', 'templates')
CONFIG = os.path.join(ROOT, 'research', 'tools', 'changemap.config.json')

BRANCH_STATUS = ('active', 'paused', 'in review', 'merged', 'abandoned')
BRANCH_LIST_KEYS = ('owner', 'areas', 'files', 'interfaces', 'cards', 'docs', 'work_queue')
BRANCH_REQUIRED = ('branch', 'owner', 'status', 'started', 'goal', 'work_queue')
QUEUE = os.path.join(DOCS, 'plan-work-queue.md')
QUEUE_DONE = os.path.join(DOCS, 'plan-work-queue-done.md')
QUEUE_SECTIONS = ('Now', 'Next', 'Later')
QUEUE_KINDS = ('bug', 'fix', 'feature', 'research', 'chore')
QUEUE_STATES = ('open', 'in progress', 'blocked', 'found', 'confirmed', 'fix built', 'built', 'run', 'verified')
QUEUE_DONE_STATES = ('done', 'dropped')
QID_RE = re.compile(r'^Q-\d+$')
QUEUE_MAX_ROW = 400
BRANCH_SECTIONS = ('Goal and scope', 'Planned changes', 'State', 'Conflicts with other branches', 'Merge plan',
                   'Log')

STATUS = {
    'active': 'in the code; the default columns say whether it is on',
    'rejected': 'measured or reviewed, not kept; code may remain behind a switch that is off, or was never built',
    'reverted': 'code removed again',
    'superseded': 'replaced by another card (superseded_by)',
    'diagnostic': 'measurement or debug aid, no product behaviour when off',
    'chore': 'commits with no behaviour of their own (refactors, build fixes, comments, tests)',
}
DEFAULTS = ('on', 'off', 'n/a', 'mixed')
LIST_KEYS = ('commits', 'prs', 'files', 'symbols', 'switches', 'tests', 'docs', 'depends_on',
             'conflicts_with', 'supersedes', 'related', 'owner', 'queue')
SECTIONS = ('What it does', 'Invariants', 'Interactions', 'Evidence', 'History and pitfalls')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.+_-]*$')
LINK_RE = re.compile(r'(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
MAX_SCAN_BYTES = 2 * 1024 * 1024
PLACEHOLDER = '{' * 2  # BOOTSTRAP.md's setup placeholders; spelled this way so its grep skips this file


def load_config():
    cfg = {
        'base_ref': '',
        'upstream_ref': '',
        'branches': ['main'],
        'code_paths': ['src'],
        'skip_paths': [],
        'switch_patterns': [],
        'default_keys': ['default'],
        'areas': {'tooling': 'research tools, diagnostics, CI, build scripts (no product behaviour)'},
        'test_id_patterns': [r'\bT-[A-Za-z0-9][A-Za-z0-9.]*(?:-[A-Za-z0-9.]+)*'],
        'link_check': ['AGENTS.md', 'CLAUDE.md', 'README.md', 'research/docs', 'research/changes',
                       'research/branches', '.claude/skills'],
        'remote': 'origin',
        'branch_docs_exempt': ['docs/*', 'dependabot/*'],
        'queue_stale_days': 7,
    }
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding='utf-8') as f:
            cfg.update({k: v for k, v in json.load(f).items() if not k.startswith('_')})
    return cfg


C = load_config()
AREAS = C['areas']
REQUIRED = ('id', 'title', 'area', 'status', 'origin') + tuple(C['default_keys'])
TEST_RES = [re.compile(p) for p in C['test_id_patterns']]
SWITCH_RES = [re.compile(p) for p in C['switch_patterns']]


def git(*args, check=True):
    out = subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True,
                         encoding='utf-8', errors='replace')
    if check and out.returncode != 0:
        raise SystemExit('git %s failed: %s' % (' '.join(args), out.stderr.strip()))
    return out.stdout if out.returncode == 0 else None


def has_history():
    return git('rev-parse', '--verify', '--quiet', 'HEAD', check=False) is not None


def ref_exists(ref):
    return bool(ref) and git('rev-parse', '--verify', '--quiet', ref + '^{commit}', check=False) is not None


def resolve_branch(b):
    """A configured branch: local first, then origin/<b> (CI checkouts often only have the remote one)."""
    for ref in (b, 'origin/' + b):
        if ref_exists(ref):
            return ref
    return None


def norm(path):
    return path.replace('\\', '/')


def is_code_path(path):
    if any(path.startswith(s) for s in C['skip_paths']):
        return False
    return any(path == d or path.startswith(d.rstrip('/') + '/') for d in C['code_paths'])


def tracked_files():
    return set(norm(p) for p in (git('ls-files', check=False) or '').splitlines())


# ---------------------------------------------------------------- facts

def facts(quiet=False):
    os.makedirs(FACTS, exist_ok=True)
    rows = commit_rows()
    with open(os.path.join(FACTS, 'commits.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# hash\tdate\tkind\tbranches\tauthor\tsubject\tfiles  (generated by changemap.py facts)\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')

    here = switch_sites(None)
    up = switch_sites(C['upstream_ref']) if ref_exists(C['upstream_ref']) else {}
    with open(os.path.join(FACTS, 'switches.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# name\torigin\tsites  (origin: upstream = also in upstream_ref; generated)\n')
        for name in sorted(here):
            f.write('%s\t%s\t%s\n' % (name, 'upstream' if name in up else 'ours', ' '.join(here[name][:12])))

    with open(os.path.join(FACTS, 'headings.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# file\tline\tlevel\tanchor\theading  (generated)\n')
        for doc in doc_files():
            for line, level, anchor, text in headings(os.path.join(DOCS, doc)):
                f.write('%s\t%d\t%d\t%s\t%s\n' % (doc, line, level, anchor, text.replace('\t', ' ')))

    with open(os.path.join(FACTS, 'tests.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('# id\tfile\tline\tanchor (enclosing heading)\ttext  (generated)\n')
        for tid, doc, line, anchor, text in all_test_sites():
            f.write('%s\t%s\t%d\t%s\t%s\n' % (tid, doc, line, anchor, text))
    if not quiet:
        n_code = sum(1 for r in rows if r[2] == 'code')
        print('facts: %d commits (%d code), %d switches in code (%d ours) -> %s'
              % (len(rows), n_code, len(here), sum(1 for n in here if n not in up), os.path.relpath(FACTS, ROOT)))


def commit_rows():
    """Commits on the configured branches and every local branch, after base_ref."""
    if not has_history():
        return []
    main_refs = [r for r in (resolve_branch(b) for b in C['branches']) if r]
    local = [b for b in (git('for-each-ref', '--format=%(refname:short)', 'refs/heads') or '').split()
             if not b.startswith('worktree-')]
    refs = list(dict.fromkeys(main_refs + local))
    if not refs:
        return []
    base = C['base_ref'] if ref_exists(C['base_ref']) else ''
    member = defaultdict(set)
    for ref in refs:
        rng = '%s..%s' % (base, ref) if base else ref
        for h in (git('rev-list', rng) or '').split():
            member[h].add(ref)
    args = ['log', '--name-only', '--format=\x01%H\x02%P\x02%ad\x02%an\x02%s', '--date=short'] + refs
    if base:
        args += ['--not', base]
    rows, seen = [], set()
    for block in git(*args).split('\x01')[1:]:
        head, _, rest = block.partition('\n')
        h, parents, date, author, subject = head.split('\x02', 4)
        if h in seen:
            continue
        seen.add(h)
        files = [norm(f) for f in rest.split('\n') if f.strip()]
        if len(parents.split()) > 1:
            kind = 'merge'
        elif any(is_code_path(f) for f in files):
            kind = 'code'
        else:
            kind = 'docs'
        on_main = sorted(b for b in C['branches'] if b in member[h] or 'origin/' + b in member[h])
        tag = ','.join(on_main) if on_main else ','.join(sorted(member[h]))
        rows.append((h[:10], date, kind, tag, author.replace('\t', ' '), subject.replace('\t', ' '),
                     ';'.join(files)))
    rows.sort(key=lambda r: r[1])
    return rows


def switch_sites(rev):
    """Switch names matched by switch_patterns in the code: the working tree, or a revision."""
    sites = defaultdict(list)
    if not SWITCH_RES:
        return sites
    for path, text in code_texts(rev):
        for n, line in enumerate(text.splitlines(), 1):
            for rx in SWITCH_RES:
                for m in rx.finditer(line):
                    name = m.group(1) if m.groups() else m.group(0)
                    sites[name.strip('"\'')].append('%s:%d' % (path, n))
    return sites


def code_texts(rev):
    if rev is None:
        for p in sorted(tracked_files()):
            if is_code_path(p) and os.path.isfile(os.path.join(ROOT, p)):
                with open(os.path.join(ROOT, p), 'rb') as f:
                    data = f.read(MAX_SCAN_BYTES + 1)
                if len(data) <= MAX_SCAN_BYTES and b'\0' not in data[:8000]:
                    yield p, data.decode('utf-8', 'replace')
        return
    names = [norm(p) for p in (git('ls-tree', '-r', '--name-only', rev, check=False) or '').splitlines()
             if is_code_path(norm(p))]
    if not names:
        return
    out = subprocess.run(['git', '-C', ROOT, 'cat-file', '--batch'], capture_output=True,
                         input=''.join('%s:%s\n' % (rev, p) for p in names).encode('utf-8')).stdout
    pos = 0
    for p in names:
        nl = out.index(b'\n', pos)
        header = out[pos:nl].split()
        pos = nl + 1
        if len(header) < 3 or header[1] != b'blob':
            continue
        size = int(header[2])
        data = out[pos:pos + size]
        pos += size + 1
        if size <= MAX_SCAN_BYTES and b'\0' not in data[:8000]:
            yield p, data.decode('utf-8', 'replace')


def doc_files():
    return sorted(d for d in os.listdir(DOCS) if d.endswith('.md')) if os.path.isdir(DOCS) else []


def slug(text):
    s = text.strip().lower()
    s = re.sub(r'[^\w\- ]', '', s, flags=re.UNICODE)
    return s.replace(' ', '-')


def headings(path):
    out, count, fence = [], defaultdict(int), False
    with open(path, encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, 1):
            if line.lstrip().startswith('```'):
                fence = not fence
                continue
            if fence:
                continue
            m = re.match(r'^(#{1,6})\s+(.*?)\s*#*\s*$', line)
            if m:
                text = m.group(2)
                base = slug(re.sub(r'`|\*\*|\[([^\]]*)\]\([^)]*\)', r'\1', text))
                n = count[base]
                count[base] += 1
                out.append((i, len(m.group(1)), base if n == 0 else '%s-%d' % (base, n), text))
    return out


def test_sites(path):
    """Test write-ups: a heading naming a test ID, or a paragraph / bullet starting with a bold test ID."""
    heads = {line: anchor for line, level, anchor, text in headings(path)}
    out, anchor, fence = [], '', False
    with open(path, encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, 1):
            if line.lstrip().startswith('```'):
                fence = not fence
            if fence:
                continue
            if i in heads:
                anchor = heads[i]
                text = line.lstrip('#').strip()
            else:
                m = re.match(r'^\s*(?:[-*] )?\*\*(.{0,120})', line)
                if not m or not any(rx.match(m.group(1)) for rx in TEST_RES):
                    continue
                text = m.group(1)
            for tid in sorted(set(t for rx in TEST_RES for t in rx.findall(text[:60]))):
                out.append((tid, i, anchor, text[:100].replace('\t', ' ')))
    return out


def all_test_sites():
    for doc in doc_files():
        for tid, line, anchor, text in test_sites(os.path.join(DOCS, doc)):
            yield tid, doc, line, anchor, text


def load_tsv(name):
    path = os.path.join(FACTS, name)
    if not os.path.exists(path):
        facts(quiet=True)
    with open(path, encoding='utf-8') as f:
        return [l.rstrip('\n').split('\t') for l in f if not l.startswith('#') and l.strip()]


# ---------------------------------------------------------------- cards

def parse_front(text, list_keys):
    """Front matter between --- lines: `key: value`, comma-separated lists for list_keys."""
    text = text.replace('\r\n', '\n')
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    if not m:
        return None, text, ['no front matter']
    meta, errors = {}, []
    for n, line in enumerate(m.group(1).split('\n'), 2):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        k, sep, v = line.partition(':')
        if not sep:
            errors.append('line %d: not "key: value"' % n)
            continue
        k, v = k.strip(), v.strip()
        meta[k] = [x.strip() for x in v.split(',') if x.strip()] if k in list_keys else v
        if any(x.startswith('<') for x in (meta[k] if isinstance(meta[k], list) else [v])):
            errors.append('%s: fill in the template\'s <...>' % k)
    return meta, m.group(2), errors


def parse_card(path):
    with open(path, encoding='utf-8') as f:
        meta, body, errors = parse_front(f.read(), LIST_KEYS)
    if meta is not None:
        meta['_path'] = path
        meta['_rel'] = norm(os.path.relpath(path, CHANGES))
    return meta, body, errors


def cards():
    out = []
    for area in sorted(os.listdir(CHANGES)) if os.path.isdir(CHANGES) else []:
        d = os.path.join(CHANGES, area)
        if area.startswith('_') or not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith('.md'):
                meta, body, errors = parse_card(os.path.join(d, name))
                out.append((meta or {'_path': os.path.join(d, name), '_rel': '%s/%s' % (area, name)},
                            body, errors))
    return out


def section(body, title):
    m = re.search(r'^## %s\s*\n(.*?)(?=^## |\Z)' % re.escape(title), body, re.S | re.M)
    return m.group(1).strip() if m else ''


def commit_hits(meta, short):
    return any(short.startswith(c) or c.startswith(short) for c in meta.get('commits', []))


def defaults_text(meta):
    return ' / '.join(meta.get(k, '?') for k in C['default_keys'])


# ---------------------------------------------------------------- index

def render_index(cs):
    by_area = defaultdict(list)
    for meta, body, _ in cs:
        by_area[meta.get('area', '?')].append(meta)
    dk = C['default_keys']
    head = 'Default' if dk == ['default'] else ' / '.join(k.replace('default_', '') for k in dk)
    lines = ['# Change index (generated by `research/tools/changemap.py index`; do not edit)', '',
             'One line per card. Open a card for invariants, interactions and evidence; look up without',
             'reading: `changemap.py file <path>` / `switch <name>` / `commit <hash>` / `test <id>` / `find <text>`.',
             'Card format and statuses: [README.md](README.md).', '',
             '%d cards.' % len(cs), '']
    for area in list(AREAS) + sorted(a for a in by_area if a not in AREAS):
        rows = by_area.get(area)
        if not rows:
            continue
        lines += ['## %s' % area, '', '_%s_' % AREAS.get(area, 'unknown area'), '',
                  '| ID | Status | %s | Switches | Title |' % head, '|---|---|---|---|---|']
        for meta in sorted(rows, key=lambda m: m.get('id', '').lower()):
            sw = ', '.join(meta.get('switches', [])[:3]) + (' …' if len(meta.get('switches', [])) > 3 else '')
            lines.append('| [%s](%s) | %s | %s | %s | %s |' % (
                meta.get('id', '?'), meta['_rel'], meta.get('status', '?'), defaults_text(meta),
                sw.replace('|', '\\|'), meta.get('title', '').replace('|', '\\|')))
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def render_tests(cs):
    tests = defaultdict(list)
    for tid, doc, line, anchor, text in all_test_sites():
        tests[tid].append((doc, line, anchor, text))
    cited = defaultdict(list)
    for meta, _, _ in cs:
        for t in meta.get('tests', []):
            cited[t].append(meta.get('id', '?'))
    tl = ['# Test IDs (generated by `research/tools/changemap.py index`; do not edit)', '',
          'Every doc heading (or bold paragraph start) that names a test run, with its anchor; cards citing it last.',
          'Before using a new ID: `changemap.py test <id>` must find nothing.', '',
          '| ID | Where | Text | Cards |', '|---|---|---|---|']

    def key(t):
        return [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', t)]
    for tid in sorted(tests, key=key):
        for doc, line, anchor, text in tests[tid]:
            tl.append('| %s | [%s:%s](../docs/%s#%s) | %s | %s |' % (
                tid, doc, line, doc, anchor, text[:80].replace('|', '\\|'), ', '.join(cited.get(tid, []))))
    return '\n'.join(tl).rstrip() + '\n'


def index():
    cs = cards()
    for name, text in (('INDEX.md', render_index(cs)), ('TESTS.md', render_tests(cs))):
        with open(os.path.join(CHANGES, name), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print('index: %d cards, %d test IDs' % (len(cs), len(set(t[0] for t in all_test_sites()))))


# ---------------------------------------------------------------- check

def check(list_all=False, only_area=None):
    facts(quiet=True)
    cs = cards()
    commits = load_tsv('commits.tsv')
    switches = {r[0]: r for r in load_tsv('switches.tsv')}
    tracked = tracked_files()
    errors = []
    ids = defaultdict(list)
    file_cache = {}

    def read(p):
        if p not in file_cache:
            try:
                with open(os.path.join(ROOT, p), encoding='utf-8', errors='replace') as f:
                    file_cache[p] = f.read()
            except OSError:
                file_cache[p] = None
        return file_cache[p]

    for meta, body, perr in cs:
        rel = meta['_rel']
        if only_area and not rel.startswith(only_area + '/'):
            continue
        e = lambda msg, rel=rel: errors.append('%s: %s' % (rel, msg))
        for x in perr:
            e(x)
        for k in REQUIRED:
            if not meta.get(k):
                e('missing %s' % k)
        cid = meta.get('id', '')
        ids[cid].append(rel)
        if cid and not ID_RE.match(cid):
            e('bad id %r' % cid)
        if cid and os.path.basename(rel) != cid.lower() + '.md':
            e('file name should be %s.md' % cid.lower())
        if meta.get('area') and meta['area'] not in AREAS:
            e('unknown area %r (areas are set in changemap.config.json)' % meta['area'])
        if meta.get('area') and not rel.startswith(meta['area'] + '/'):
            e('card is not in its area folder')
        if meta.get('status') and meta['status'] not in STATUS:
            e('unknown status %r' % meta['status'])
        for k in C['default_keys']:
            if meta.get(k) and meta[k] not in DEFAULTS:
                e('%s must be one of %s' % (k, '/'.join(DEFAULTS)))
        if meta.get('status') == 'superseded' and not meta.get('superseded_by'):
            e('superseded without superseded_by')
        gone = meta.get('status') == 'reverted'
        for s in SECTIONS:
            if meta.get('status') != 'chore' and not section(body, s):
                e('empty or missing section "## %s"' % s)
        if PLACEHOLDER in body or any(PLACEHOLDER in str(v) for v in meta.values()):
            e('setup placeholder (two opening braces) left in the card')
        for c in meta.get('commits', []):
            if not re.match(r'^[0-9a-f]{7,40}$', c):
                e('bad commit %r' % c)
            elif not any(r[0].startswith(c) or c.startswith(r[0]) for r in commits):
                if not has_history() or subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', c + '^{commit}'],
                                                       capture_output=True).returncode != 0:
                    e('commit %s does not exist (squash or rebase merges rewrite hashes: see repo-boundaries.md)'
                      % c)
        for pr in meta.get('prs', []):
            if not re.match(r'^(#\d+|https?://\S+)$', pr):
                e('bad pr %r (use #12 or a URL)' % pr)
        for p in meta.get('files', []):
            if p not in tracked and not gone:
                e('file %s not in the repo (git ls-files)' % p)
        for sym in meta.get('symbols', []):
            if gone:
                continue
            rx = re.compile(r'\b%s\b' % re.escape(sym.split('::')[-1].split('.')[-1].rstrip('()')))
            if not any(read(p) and rx.search(read(p)) for p in meta.get('files', [])):
                e('symbol %s not found in the card\'s files' % sym)
        for sw in meta.get('switches', []):
            if sw not in switches and not gone:
                e('switch %s not found in the code (switch_patterns in changemap.config.json)' % sw)
        for d in meta.get('docs', []):
            doc, _, anchor = d.partition('#')
            path = os.path.join(DOCS, doc) if os.path.exists(os.path.join(DOCS, doc)) else os.path.join(ROOT, doc)
            if not os.path.exists(path):
                e('doc %s not found (under research/docs/ or the repo root)' % doc)
            elif anchor and doc.endswith('.md') and anchor not in set(h[2] for h in headings(path)):
                e('anchor %s not in %s (changemap.py doc %s lists them)' % (anchor, doc, doc))
    known = set(m.get('id', '') for m, _, _ in cs)
    for meta, body, _ in cs:
        if only_area and not meta['_rel'].startswith(only_area + '/'):
            continue
        for k in ('depends_on', 'conflicts_with', 'supersedes', 'related'):
            for ref in meta.get(k, []):
                if ref not in known:
                    errors.append('%s: %s refers to unknown card %s' % (meta['_rel'], k, ref))
        if meta.get('superseded_by') and meta['superseded_by'] not in known:
            errors.append('%s: superseded_by unknown card %s' % (meta['_rel'], meta['superseded_by']))
    for cid, rels in ids.items():
        if cid and len(rels) > 1:
            errors.append('id %s used by %s' % (cid, ', '.join(rels)))

    if not only_area:
        errors += check_links()
        errors += check_branch_docs(set(m.get('id', '') for m, _, _ in cs))
        errors += check_queue(cs)
        for name, text in (('INDEX.md', render_index(cs)), ('TESTS.md', render_tests(cs))):
            path = os.path.join(CHANGES, name)
            old = open(path, encoding='utf-8').read().replace('\r\n', '\n') if os.path.exists(path) else ''
            if old != text:
                errors.append('research/changes/%s is out of date: run "changemap.py index"' % name)

    # Coverage (reported, not errors)
    covered_commits = set(c[:7] for meta, _, _ in cs for c in meta.get('commits', []))
    on_main = [r for r in commits if r[2] == 'code' and set(r[3].split(',')) & set(C['branches'])]
    uncovered = [r for r in on_main if r[0][:7] not in covered_commits]
    covered_sw = set(sw for meta, _, _ in cs for sw in meta.get('switches', []))
    ours = [n for n, r in switches.items() if r[1] == 'ours']
    unsw = [n for n in ours if n not in covered_sw]
    for msg in errors:
        print('ERROR', msg)
    print('\n%d cards, %d errors' % (len(cs), len(errors)))
    print('code commits on %s without a card: %d of %d' % ('/'.join(C['branches']), len(uncovered), len(on_main)))
    if SWITCH_RES:
        print('switches without a card: %d of %d' % (len(unsw), len(ours)))
    if list_all:
        for r in uncovered:
            print('  commit %s %s %s: %s' % (r[0], r[1], r[4], r[5][:90]))
        for n in sorted(unsw):
            print('  switch %s %s' % (n, switches[n][2].split(' ')[0]))
    return 1 if errors else 0


def link_sources():
    for entry in C['link_check']:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield path
        elif os.path.isdir(path):
            for d, dirs, files in os.walk(path):
                dirs[:] = [x for x in dirs if not x.startswith('_') and x != 'data']
                for name in files:
                    if name.endswith('.md'):
                        yield os.path.join(d, name)


def check_links():
    """Relative links in the docs must reach a file, and an anchor in a .md target must exist."""
    errors, anchor_cache = [], {}
    for src in link_sources():
        fence = False
        with open(src, encoding='utf-8', errors='replace') as f:
            for n, line in enumerate(f, 1):
                if line.lstrip().startswith('```'):
                    fence = not fence
                    continue
                if fence:
                    continue
                for target in LINK_RE.findall(re.sub(r'`[^`]*`', '', line)):
                    if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or PLACEHOLDER in target or target.startswith('<'):
                        continue
                    path, _, anchor = target.partition('#')
                    full = os.path.normpath(os.path.join(os.path.dirname(src), path)) if path else src
                    where = '%s:%d' % (norm(os.path.relpath(src, ROOT)), n)
                    if not os.path.exists(full):
                        errors.append('%s: broken link %s' % (where, target))
                    elif anchor and full.endswith('.md'):
                        if full not in anchor_cache:
                            anchor_cache[full] = set(h[2] for h in headings(full))
                        if anchor not in anchor_cache[full]:
                            errors.append('%s: no heading #%s in %s' % (where, anchor, path or 'this file'))
    return errors


# ---------------------------------------------------------------- branches

def branch_doc_path(name):
    return os.path.join(BRANCH_DOCS, *name.split('/')) + '.md'


def current_branch():
    """The branch being worked on; in GitHub Actions the PR's head branch or the pushed branch."""
    env = os.environ.get('GITHUB_HEAD_REF') or (
        os.environ.get('GITHUB_REF_NAME', '') if os.environ.get('GITHUB_REF_TYPE') == 'branch' else '')
    if env:
        return env
    return (git('symbolic-ref', '--short', '-q', 'HEAD', check=False) or '').strip()


def branch_exempt(name):
    return not name or name in C['branches'] or any(fnmatch.fnmatch(name, p) for p in C['branch_docs_exempt'])


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) or (p.rstrip('/*') and path.startswith(p.rstrip('/*') + '/'))
               for p in patterns)


def branch_docs():
    """Reference files in the working tree: (branch name, meta, body, errors)."""
    out = []
    for d, dirs, files in os.walk(BRANCH_DOCS) if os.path.isdir(BRANCH_DOCS) else []:
        dirs.sort()
        for f in sorted(files):
            if not f.endswith('.md') or (d == BRANCH_DOCS and f == 'README.md'):
                continue
            path = os.path.join(d, f)
            with open(path, encoding='utf-8') as fh:
                meta, body, errs = parse_front(fh.read(), BRANCH_LIST_KEYS)
            out.append((norm(os.path.relpath(path, BRANCH_DOCS))[:-3], meta, body, errs))
    return out


def check_branch_docs(known_cards):
    errors = []
    for name, meta, body, errs in branch_docs():
        e = lambda msg, name=name: errors.append('research/branches/%s.md: %s' % (name, msg))
        for x in errs:
            e(x)
        if meta is None:
            continue
        for k in BRANCH_REQUIRED:
            if not meta.get(k):
                e('missing %s' % k)
        if meta.get('branch') and meta['branch'] != name:
            e('branch: %s does not match the file path (research/branches/<branch>.md)' % meta['branch'])
        if meta.get('status') and meta['status'] not in BRANCH_STATUS:
            e('status must be one of: %s' % ', '.join(BRANCH_STATUS))
        if meta.get('started') and not re.match(r'^\d{4}-\d{2}-\d{2}$', meta['started']):
            e('started must be YYYY-MM-DD')
        for a in meta.get('areas', []):
            if a not in AREAS:
                e('unknown area %s' % a)
        for c in meta.get('cards', []):
            if c not in known_cards:
                e('unknown card %s' % c)
        for d in meta.get('docs', []):
            doc = d.partition('#')[0]
            if not os.path.exists(os.path.join(DOCS, doc)) and not os.path.exists(os.path.join(ROOT, doc)):
                e('doc %s not found' % doc)
        for s in BRANCH_SECTIONS:
            if not re.search(r'^## %s\s*$' % re.escape(s), body, re.M):
                e('missing section "## %s"' % s)
        if PLACEHOLDER in body:
            e('setup placeholder (two opening braces) left in the file')
    cur = current_branch()
    if not branch_exempt(cur) and not os.path.exists(branch_doc_path(cur)):
        errors.append('branch %s has no reference file research/branches/%s.md: run "changemap.py new-branch %s"'
                      % (cur, cur, cur))
    return errors


def changed_since_base(ref, main):
    base = (git('merge-base', main, ref, check=False) or '').strip()
    if not base:
        return set()
    return set(norm(f) for f in (git('diff', '--name-only', base, ref, check=False) or '').splitlines() if f)


def merge_conflicts(a, b):
    """Files that would conflict if a and b were merged now; None when git is older than 2.38."""
    r = subprocess.run(['git', '-C', ROOT, 'merge-tree', '--write-tree', '--name-only', '--no-messages', a, b],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode == 0:
        return []
    if r.returncode == 1:
        return sorted(set(l for l in r.stdout.splitlines()[1:] if l.strip()))
    return None


def short_list(items, n=8):
    items = list(items)
    return ', '.join(items[:n]) + (' (+%d more)' % (len(items) - n) if len(items) > n else '')


def cmd_branches(args):
    if not has_history():
        raise SystemExit('no git history yet')
    remote = C['remote']
    has_remote = remote in (git('remote', check=False) or '').split()
    if has_remote and '--no-fetch' not in args:
        r = subprocess.run(['git', '-C', ROOT, 'fetch', '--prune', '--quiet', remote], capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            print('warning: git fetch %s failed, using the last fetched state: %s' % (remote, r.stderr.strip()[:200]))
    main = resolve_branch(C['branches'][0])
    if not main:
        raise SystemExit('main branch %s not found' % C['branches'][0])
    cur = current_branch()
    working = cur and not branch_exempt(cur)
    mine, my_meta = set(), {}
    if working:
        mine = changed_since_base('HEAD', main)
        mine |= set(norm(f) for f in (git('diff', '--name-only', 'HEAD', check=False) or '').splitlines() if f)
        mine |= set(norm(f) for f in (git('ls-files', '--others', '--exclude-standard', check=False) or '')
                    .splitlines() if f)
        if os.path.exists(branch_doc_path(cur)):
            with open(branch_doc_path(cur), encoding='utf-8') as f:
                my_meta = parse_front(f.read(), BRANCH_LIST_KEYS)[0] or {}
    my_plan, my_areas = my_meta.get('files', []), set(my_meta.get('areas', []))
    print('You are on %s%s' % (cur or '(detached HEAD)', '' if not working else
          '; reference file %s; %d files changed vs %s' % (
              'ok' if my_meta else 'MISSING (changemap.py new-branch %s)' % cur, len(mine), main)))
    if working:
        conflicts = merge_conflicts(main, 'HEAD')
        if conflicts:
            print('    CONFLICTS with %s now: %s (merge %s into your branch and resolve them)'
                  % (main, short_list(conflicts), main))

    refs = [(n, '%s/%s' % (remote, n)) for n in sorted(
        r[len(remote) + 1:] for r in (git('for-each-ref', '--format=%(refname:short)', 'refs/remotes/' + remote,
                                          check=False) or '').split() if r.startswith(remote + '/'))
        if n != 'HEAD' and n != cur and n not in C['branches']] if has_remote else []
    pushed = set(n for n, _ in refs)
    for b in (git('for-each-ref', '--format=%(refname:short)', 'refs/heads', check=False) or '').split():
        if b != cur and b not in C['branches'] and b not in pushed and not b.startswith('worktree-'):
            refs.append((b, b))
    active, merged, undocumented = 0, [], []
    for name, ref in refs:
        if git('merge-base', '--is-ancestor', ref, main, check=False) is not None:
            merged.append(name)
            continue
        active += 1
        text = git('show', '%s:research/branches/%s.md' % (ref, name), check=False)
        meta = (parse_front(text, BRANCH_LIST_KEYS)[0] if text else None) or {}
        files = changed_since_base(ref, main)
        last = (git('log', '-1', '--format=%ad %an', '--date=short', ref, check=False) or '').strip()
        where = '' if ref != name else '  (local only: nobody else can see it until it is pushed)'
        if meta:
            print('\n%s  [%s] %s: %s%s' % (name, meta.get('status', '?'), ', '.join(meta.get('owner', [])),
                                          meta.get('goal', ''), where))
        else:
            print('\n%s  [no reference file]%s' % (name, where))
            if not branch_exempt(name):
                undocumented.append(name)
        print('    last commit %s; %d files changed vs %s%s' % (
            last, len(files), main, '; work queue %s' % ', '.join(meta['work_queue']) if meta.get('work_queue') else ''))
        if meta.get('interfaces'):
            print('    changes interfaces: %s' % short_list(meta['interfaces']))
        if not working:
            continue
        theirs = meta.get('files', [])
        both = sorted(files & mine)
        on_my_plan = sorted(f for f in files - mine if my_plan and matches(f, my_plan))
        on_their_plan = sorted(f for f in mine - files if theirs and matches(f, theirs))
        areas = sorted(my_areas & set(meta.get('areas', [])))
        if both:
            print('    OVERLAP, both change: %s' % short_list(both))
        if on_my_plan:
            print('    they change files you plan to change: %s' % short_list(on_my_plan))
        if on_their_plan:
            print('    you change files they plan to change: %s' % short_list(on_their_plan))
        if areas:
            print('    same areas: %s' % ', '.join(areas))
        conflicts = merge_conflicts('HEAD', ref)
        if conflicts:
            print('    CONFLICTS if merged now: %s' % short_list(conflicts))
        elif conflicts == [] and both:
            print('    merges cleanly with yours today (git merge-tree)')
    print('\n%d active branch%s besides yours.' % (active, '' if active == 1 else 'es'))
    if merged:
        print('No commits beyond %s (merged, or not started; delete only with the owner\'s go): %s'
              % (main, ', '.join(merged)))
    if undocumented:
        print('No reference file (ask the owner): %s' % ', '.join(undocumented))
    if working:
        print('Record each overlap in research/branches/%s.md, "Conflicts with other branches", with today\'s date.'
              % cur)


def cmd_new_branch(name):
    if not re.match(r'^[A-Za-z0-9._/-]+$', name) or '..' in name or name.startswith('/') or name.endswith('/'):
        raise SystemExit('bad branch name %r' % name)
    if branch_exempt(name):
        print('note: %s needs no reference file (main or branch_docs_exempt); writing one anyway' % name)
    path = branch_doc_path(name)
    if os.path.exists(path):
        raise SystemExit('%s exists' % norm(os.path.relpath(path, ROOT)))
    with open(os.path.join(TEMPLATES, 'branch.md'), encoding='utf-8') as f:
        text = f.read()
    main = resolve_branch(C['branches'][0]) if has_history() else None
    base = (git('rev-parse', '--short', main, check=False) or '').strip() if main else ''
    owner = (git('config', 'user.name', check=False) or '').strip()
    fill = {'branch': name, 'started': datetime.date.today().isoformat(),
            'base': '%s @ %s' % (C['branches'][0], base) if base else '', 'owner': owner}
    for k, v in fill.items():
        if v:
            text = re.sub(r'^%s:.*$' % k, lambda m, k=k, v=v: '%s: %s' % (k, v), text, count=1, flags=re.M)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('wrote %s. Fill every <...>; run "changemap.py branches" and fill "Conflicts with other branches";'
          ' make it the branch\'s first commit and push the branch so others see it.'
          % norm(os.path.relpath(path, ROOT)))


# ---------------------------------------------------------------- work queue

def split_row(line):
    """Cells of a markdown table row; | inside backticks or escaped as \\| does not split."""
    s = line.strip()
    s = s[1:] if s.startswith('|') else s
    s = s[:-1] if s.endswith('|') and not s.endswith('\\|') else s
    cells, cur, tick, i = [], '', False, 0
    while i < len(s):
        if s[i] == '\\' and s[i + 1:i + 2] == '|':
            cur += '|'
            i += 2
            continue
        if s[i] == '`':
            tick = not tick
        if s[i] == '|' and not tick:
            cells.append(cur.strip())
            cur = ''
        else:
            cur += s[i]
        i += 1
    cells.append(cur.strip())
    return cells


def read_queue(path):
    """Rows of every table with an ID column: dicts keyed by lower-case header, plus _section, _line, _text."""
    rows, section, header, fence = [], '', None, False
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', errors='replace') as f:
        for n, line in enumerate(f, 1):
            if line.lstrip().startswith('```'):
                fence = not fence
                continue
            if fence:
                continue
            m = re.match(r'^##\s+(.*?)\s*$', line)
            if m:
                section, header = m.group(1), None
                continue
            if not line.startswith('|'):
                header = None
                continue
            cells = split_row(line)
            if header is None:
                header = [c.lower() for c in cells]
                continue
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                continue
            row = dict(zip(header, cells))
            if 'id' in row:
                row.update(_section=section, _line=n, _text=line.rstrip('\n'), _file=path)
                rows.append(row)
    return rows


def plain(text):
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    return text.replace('**', '').replace('`', '')


def state_of(row, states):
    s = row.get('state', '').lower()
    return next((x for x in states if s.startswith(x)), None)


def check_queue(cs):
    if not os.path.exists(QUEUE):
        return ['research/docs/plan-work-queue.md is missing']
    errors, seen = [], {}
    active, done = read_queue(QUEUE), read_queue(QUEUE_DONE)
    for row in active + done:
        where = '%s:%d' % (norm(os.path.relpath(row['_file'], ROOT)), row['_line'])
        e = lambda msg, where=where: errors.append('%s: %s' % (where, msg))
        qid = row.get('id', '')
        if not QID_RE.match(qid):
            e('ID must be Q-<number>, not %r' % qid)
            continue
        if qid in seen:
            e('%s is also at line %d of %s: IDs are never reused; give the newer row "changemap.py queue next"'
              % (qid, seen[qid]['_line'], os.path.basename(seen[qid]['_file'])))
        seen[qid] = row
        if row.get('kind') not in QUEUE_KINDS:
            e('%s: kind must be one of %s' % (qid, ', '.join(QUEUE_KINDS)))
        if len(row['_text']) > QUEUE_MAX_ROW:
            e('%s: row is %d characters (max %d): move the detail into the linked doc'
              % (qid, len(row['_text']), QUEUE_MAX_ROW))
        if row['_file'] == QUEUE:
            if row['_section'] not in QUEUE_SECTIONS:
                e('%s: rows belong under ## Now, ## Next or ## Later' % qid)
            if not state_of(row, QUEUE_STATES):
                e('%s: state must start with one of: %s (done / dropped rows move to plan-work-queue-done.md)'
                  % (qid, ', '.join(QUEUE_STATES)))
            if row['_section'] == 'Now' and not row.get('owner'):
                e('%s: a Now row needs an owner' % qid)
            if state_of(row, QUEUE_STATES) == 'in progress' and row['_section'] != 'Now':
                e('%s: in progress items belong under ## Now' % qid)
        else:
            st = state_of(row, QUEUE_DONE_STATES)
            if not st:
                e('%s: state must be done or dropped here' % qid)
            elif st == 'done' and not row.get('commit / pr'):
                e('%s: a done row names its commit or PR' % qid)
            elif st == 'dropped' and not row.get('result'):
                e('%s: a dropped row says why under Result' % qid)
    for meta, _, _ in cs:
        for q in meta.get('queue', []):
            if q not in seen:
                errors.append('%s: queue item %s does not exist' % (meta['_rel'], q))
    cur = current_branch()
    for name, meta, _, _ in branch_docs():
        for q in (meta or {}).get('work_queue', []):
            if q not in seen:
                errors.append('research/branches/%s.md: work_queue %s does not exist' % (name, q))
            elif name == cur and seen[q]['_file'] == QUEUE and (
                    seen[q]['_section'] != 'Now' or cur not in plain(seen[q].get('branch', ''))):
                errors.append('%s is worked on by %s but its queue row is not under ## Now with this branch in '
                              'its Branch column: update plan-work-queue.md' % (q, cur))
    return errors


def queue_branch_note(row):
    """For a Now row: a warning when its branch is missing or has gone quiet."""
    name = plain(row.get('branch', '')).strip()
    if not name or name == '-' or not has_history():
        return ''
    ref = next((r for r in (name, '%s/%s' % (C['remote'], name)) if ref_exists(r)), None)
    if not ref:
        return '  [branch not found: not pushed, or deleted]'
    when = (git('log', '-1', '--format=%ct', ref, check=False) or '').strip()
    if when:
        days = (datetime.datetime.now().timestamp() - int(when)) / 86400
        if days > C['queue_stale_days']:
            return '  [no commits for %d days: still claimed?]' % days
    return ''


def cmd_queue(args):
    active, done = read_queue(QUEUE), read_queue(QUEUE_DONE)
    nums = [int(r['id'][2:]) for r in active + done if QID_RE.match(r.get('id', ''))]
    if args and args[0] == 'next':
        print('Q-%d' % (max(nums) + 1 if nums else 1))
        return
    if args:
        return queue_item(args[0].upper(), active + done)
    for sec in ('Now', 'Next'):
        rows = [r for r in active if r['_section'] == sec]
        print('%s (%d)' % (sec, len(rows)))
        for r in rows:
            print('  %-6s %-8s %-16s %-10s %s%s' % (
                r['id'], r.get('kind', ''), plain(r.get('state', ''))[:16], plain(r.get('owner', ''))[:10],
                plain(r.get('item', ''))[:80], queue_branch_note(r) if sec == 'Now' else ''))
    print('Later: %d items. Done / dropped: %d (plan-work-queue-done.md). Next free ID: Q-%d.' % (
        sum(1 for r in active if r['_section'] == 'Later'), len(done), max(nums) + 1 if nums else 1))


def queue_item(qid, rows):
    row = next((r for r in rows if r.get('id') == qid), None)
    if not row:
        print('no queue item %s' % qid)
        return
    print('%s  (%s:%d, %s)' % (qid, norm(os.path.relpath(row['_file'], ROOT)), row['_line'],
                               row['_section'] or 'archive'))
    for k, v in row.items():
        if not k.startswith('_') and k != 'id' and v:
            print('    %s: %s' % (k, plain(v)))
    print('\nReferenced by:')
    for name, meta, _, _ in branch_docs():
        if qid in (meta or {}).get('work_queue', []):
            print('  branch file research/branches/%s.md [%s]' % (name, meta.get('status', '?')))
    if has_history():
        for r in (git('for-each-ref', '--format=%(refname:short)', 'refs/remotes/' + C['remote'], check=False)
                  or '').split():
            name = r[len(C['remote']) + 1:]
            text = git('show', '%s:research/branches/%s.md' % (r, name), check=False) if name else None
            meta = (parse_front(text, BRANCH_LIST_KEYS)[0] if text else None) or {}
            if qid in meta.get('work_queue', []) and not os.path.exists(branch_doc_path(name)):
                print('  branch %s (remote) [%s] %s' % (name, meta.get('status', '?'), ', '.join(meta.get('owner', []))))
    for meta, _, _ in cards():
        if qid in meta.get('queue', []):
            print('  card %s: %s' % (meta.get('id'), meta.get('title', '')[:80]))
    rx = re.compile(r'\b%s\b' % re.escape(qid))
    for doc in doc_files():
        path = os.path.join(DOCS, doc)
        if path in (QUEUE, QUEUE_DONE):
            continue
        with open(path, encoding='utf-8', errors='replace') as f:
            for n, line in enumerate(f, 1):
                if rx.search(line):
                    print('  research/docs/%s:%d  %s' % (doc, n, line.strip()[:90]))
    if has_history():
        for line in (git('log', '--all', '--format=%h %ad %an: %s', '--date=short', '--grep=' + qid,
                         check=False) or '').splitlines():
            if rx.search(line):
                print('  commit %s' % line[:110])


# ---------------------------------------------------------------- lookups

def brief(meta, body, invariants=True):
    print('%s [%s, %s] %s  (%s)' % (meta.get('id'), meta.get('status'), defaults_text(meta), meta.get('title'),
                                    'research/changes/' + meta['_rel']))
    if meta.get('switches'):
        print('    switches: ' + ', '.join(meta['switches']))
    if invariants:
        for line in section(body, 'Invariants').splitlines()[:8]:
            print('    ' + line)


def cmd_file(path):
    path = norm(path)
    while path.startswith('./'):
        path = path[2:]
    hits = [(m, b) for m, b, _ in cards() if any(f == path or f.endswith('/' + path) or path.endswith('/' + f)
                                                   for f in m.get('files', []))]
    for m, b in hits:
        brief(m, b)
    rows = [r for r in load_tsv('commits.tsv') if r[2] == 'code' and any(
        f == path or f.endswith('/' + path) for f in r[6].split(';'))]
    covered = set(c[:7] for m, _, _ in cards() for c in m.get('commits', []))
    loose = [r for r in rows if r[0][:7] not in covered]
    print('\n%d cards; %d commits touch it, %d without a card%s' % (len(hits), len(rows), len(loose),
          ':' if loose else ''))
    for r in loose[-15:]:
        print('  %s %s %s: %s' % (r[0], r[1], r[4], r[5][:90]))


def cmd_switch(name):
    for r in load_tsv('switches.tsv'):
        if name.lower() in r[0].lower():
            print('%s (%s): %s' % (r[0], r[1], r[2]))
    for m, b, _ in cards():
        if any(name.lower() in s.lower() for s in m.get('switches', [])):
            brief(m, b, invariants=False)


def cmd_commit(h):
    for r in load_tsv('commits.tsv'):
        if r[0].startswith(h[:10]) or h.startswith(r[0]):
            print('%s %s %s [%s] %s: %s\n  files: %s' % (r[0], r[1], r[2], r[3], r[4], r[5],
                                                       r[6].replace(';', ' ')))
    for m, b, _ in cards():
        if commit_hits(m, h[:10]):
            brief(m, b)


def cmd_test(tid):
    for t, doc, line, anchor, text in all_test_sites():
        if t.lower() == tid.lower():
            print('research/docs/%s:%s  #%s\n    %s' % (doc, line, anchor, text[:100]))
    for m, b, _ in cards():
        if tid in m.get('tests', []):
            brief(m, b, invariants=False)


def cmd_show(cid):
    for m, b, _ in cards():
        if m.get('id', '').lower() == cid.lower():
            with open(m['_path'], encoding='utf-8') as f:
                print(f.read())
            return
    print('no card %s; try: changemap.py find %s' % (cid, cid))


def cmd_find(text):
    rx = re.compile(re.escape(text), re.I)
    for m, b, _ in cards():
        if rx.search(m.get('title', '')) or rx.search(b) or rx.search(m.get('id', '')):
            brief(m, b, invariants=False)


def cmd_doc(doc):
    path = os.path.join(DOCS, os.path.basename(doc))
    if not os.path.exists(path):
        path = os.path.join(ROOT, doc)
    if not os.path.exists(path):
        print('no doc %s' % doc)
        return
    for line, level, anchor, text in headings(path):
        print('%5s %s%s  #%s' % (line, '  ' * (level - 1), text[:100], anchor))


def cmd_area(area):
    for m, b, _ in cards():
        if m.get('area') == area:
            brief(m, b, invariants=False)


def cmd_new(area, cid):
    if area not in AREAS:
        raise SystemExit('unknown area %s; areas: %s (changemap.config.json)' % (area, ', '.join(AREAS)))
    if not ID_RE.match(cid):
        raise SystemExit('bad id %r: letters, digits and . + _ - only' % cid)
    if any(m.get('id', '').lower() == cid.lower() for m, _, _ in cards()):
        raise SystemExit('id %s is taken: changemap.py show %s' % (cid, cid))
    with open(os.path.join(TEMPLATES, 'card.md'), encoding='utf-8') as f:
        text = f.read()
    text = re.sub(r'^id:.*$', 'id: %s' % cid, text, count=1, flags=re.M)
    text = re.sub(r'^area:.*$', 'area: %s' % area, text, count=1, flags=re.M)
    os.makedirs(os.path.join(CHANGES, area), exist_ok=True)
    path = os.path.join(CHANGES, area, cid.lower() + '.md')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('wrote %s: fill every <...>, then "changemap.py check" and "index"' % norm(os.path.relpath(path, ROOT)))


def main(argv):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, rest = argv[1], argv[2:]
    if cmd == 'facts':
        facts()
    elif cmd == 'index':
        index()
    elif cmd == 'check':
        area = next((a for a in rest if not a.startswith('-')), None)
        return check('--list' in rest, area)
    elif cmd == 'new' and len(rest) == 2:
        cmd_new(*rest)
    elif cmd == 'queue':
        cmd_queue(rest)
    elif cmd == 'branches':
        cmd_branches(rest)
    elif cmd == 'new-branch' and len(rest) == 1:
        cmd_new_branch(rest[0])
    elif cmd in ('file', 'switch', 'commit', 'test', 'show', 'find', 'doc', 'area') and rest:
        globals()['cmd_' + cmd](' '.join(rest))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
