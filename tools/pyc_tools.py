"""Helpers for reconstructing Python 3.14 source from a .pyc and verifying it.

Run with python3.14:
  pyc_tools.py dump   ORIG.pyc OUTDIR            # per-function disassembly + constants
  pyc_tools.py verify ORIG.pyc CANDIDATE.py [--diff QUALNAME] [--all]
"""
import dis, marshal, sys, types, difflib, os, re

def load_pyc(path):
    with open(path, 'rb') as f:
        data = f.read()
    return marshal.loads(data[16:])

def walk(co, out=None):
    if out is None:
        out = []
    out.append(co)
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            walk(c, out)
    return out

def keyed(codes):
    """qualname -> list of code objects (duplicates like __annotate__ keep order)."""
    d = {}
    for c in codes:
        d.setdefault(c.co_qualname, []).append(c)
    return d

_label = re.compile(r'\bL\d+\b')

def norm_instrs(co):
    res = []
    for ins in dis.get_instructions(co):
        if ins.opname in ('CACHE', 'NOP', 'RESUME', 'NOT_TAKEN'):
            continue
        arg = ins.argrepr
        if isinstance(ins.argval, types.CodeType):
            arg = '<code %s>' % ins.argval.co_qualname
        res.append('%s %s' % (ins.opname, arg))
    return res

def consts_sig(co):
    return [c.co_qualname if isinstance(c, types.CodeType) else c for c in co.co_consts]

def compare_one(a, b):
    ia, ib = norm_instrs(a), norm_instrs(b)
    ratio = difflib.SequenceMatcher(None, ia, ib, autojunk=False).ratio()
    exact = ia == ib
    problems = []
    if a.co_names != b.co_names:
        problems.append('names')
    if a.co_varnames != b.co_varnames:
        problems.append('varnames')
    if consts_sig(a) != consts_sig(b):
        problems.append('consts')
    if a.co_argcount != b.co_argcount or a.co_kwonlyargcount != b.co_kwonlyargcount or a.co_flags != b.co_flags:
        problems.append('signature/flags')
    return exact, ratio, problems, ia, ib

def cmd_dump(orig, outdir):
    co = load_pyc(orig)
    os.makedirs(outdir, exist_ok=True)
    idx = []
    for i, c in enumerate(walk(co)):
        lines = [l for _, _, l in c.co_lines() if l]
        name = '%03d_%s.txt' % (i, c.co_qualname.replace('<', '').replace('>', '').replace('.', '__'))
        with open(os.path.join(outdir, name), 'w') as f:
            f.write('# qualname: %s\n# firstlineno: %s  lines %s-%s\n' % (
                c.co_qualname, c.co_firstlineno, min(lines, default=0), max(lines, default=0)))
            f.write('# argcount=%d posonly=%d kwonly=%d flags=%s\n' % (
                c.co_argcount, c.co_posonlyargcount, c.co_kwonlyargcount, dis.pretty_flags(c.co_flags)))
            f.write('# varnames=%r\n# freevars=%r cellvars=%r\n# names=%r\n' % (
                c.co_varnames, c.co_freevars, c.co_cellvars, c.co_names))
            f.write('# consts:\n')
            for k in c.co_consts:
                if isinstance(k, types.CodeType):
                    f.write('#   <code %s>\n' % k.co_qualname)
                else:
                    f.write('#   %r\n' % (k,))
            f.write('\n')
            dis.dis(c, file=f, depth=0, show_caches=False)
        idx.append('%s\t%s\t%s-%s\t%d' % (name, c.co_qualname, min(lines, default=0), max(lines, default=0), len(c.co_code)))
    with open(os.path.join(outdir, 'INDEX.tsv'), 'w') as f:
        f.write('\n'.join(idx) + '\n')
    print('dumped', len(idx), 'code objects to', outdir)

def cmd_verify(orig, cand, diff_name=None, show_all=False):
    o = keyed(walk(load_pyc(orig)))
    src = open(cand, encoding='utf-8').read()
    try:
        cc = compile(src, os.path.basename(orig).replace('.pyc', '.py'), 'exec')
    except SyntaxError as e:
        print('SYNTAX ERROR:', e)
        return 2
    c = keyed(walk(cc))
    total = exact_n = 0
    rows = []
    for q, lst in c.items():
        if q == '<module>' and q not in o:
            continue
        olst = o.get(q)
        if not olst:
            rows.append((q, 'NOT IN ORIGINAL', 0.0, []))
            continue
        for i, cobj in enumerate(lst):
            if i >= len(olst):
                rows.append((q, 'EXTRA DUPLICATE', 0.0, []))
                continue
            ex, r, probs, ia, ib = compare_one(olst[i], cobj)
            total += 1
            exact_n += ex and not probs
            rows.append((q, 'OK' if ex and not probs else 'DIFF', r, probs))
            if diff_name and q == diff_name:
                print('\n'.join(difflib.unified_diff(ia, ib, 'original', 'candidate', lineterm='', n=3)))
                if probs:
                    a = olst[i]
                    for p in probs:
                        if p == 'names': print('orig names', a.co_names, '\ncand names', cobj.co_names)
                        if p == 'varnames': print('orig varnames', a.co_varnames, '\ncand varnames', cobj.co_varnames)
                        if p == 'consts': print('orig consts', consts_sig(a), '\ncand consts', consts_sig(cobj))
                        if p == 'signature/flags': print('orig', a.co_argcount, a.co_kwonlyargcount, dis.pretty_flags(a.co_flags), '\ncand', cobj.co_argcount, cobj.co_kwonlyargcount, dis.pretty_flags(cobj.co_flags))
    for q, st, r, probs in rows:
        if show_all or st != 'OK':
            print('%-70s %-16s %.3f %s' % (q, st, r, ','.join(probs)))
    missing = [q for q in o if q not in c]
    print('\nexact matches: %d / %d compared' % (exact_n, total))
    if show_all:
        print('original code objects not present in candidate:', len(missing))
    return 0

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'dump':
        cmd_dump(a[1], a[2])
    elif a[0] == 'verify':
        dn = a[a.index('--diff') + 1] if '--diff' in a else None
        sys.exit(cmd_verify(a[1], a[2], dn, '--all' in a))
