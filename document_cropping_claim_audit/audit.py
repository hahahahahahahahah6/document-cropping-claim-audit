"""Read-only documentation and AST evidence analysis."""
import ast
import os
from pathlib import Path
import re

from .phrases import DOCUMENTCROPPING, NODOCUMENTCROPPING, GENERIC_NAMES


def normalize(text):
    text = text.lower().replace('’', "'")
    text = text.replace("can't", 'can not').replace("won't", 'will not')
    text = text.replace("n't", ' not')
    for suffix, expansion in (("'re", ' are'), ("'ve", ' have'), ("'ll", ' will'),
                              ("'d", ' would'), ("'m", ' am'), ("'s", ' is')):
        text = text.replace(suffix, expansion)
    return ' '.join(text.replace('-', ' ').split())


def pattern(phrases):
    return re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in
                      sorted(phrases, key=lambda p: (-len(p), p))) + r')\b')


YES = pattern(DOCUMENTCROPPING)
NO = pattern(NODOCUMENTCROPPING)


def paragraphs(text):
    """Yield (starting line, prose), excluding CommonMark-style fences."""
    fence = None
    lines = []
    start = 1
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker and not (marker[1][0] == '`' and '`' in marker[2]):
            if lines:
                yield start, '\n'.join(lines)
                lines = []
            fence = (marker[1][0], len(marker[1]))
        elif not line.strip():
            if lines:
                yield start, '\n'.join(lines)
                lines = []
        else:
            if not lines:
                start = number
            lines.append(line)
    if lines:
        yield start, '\n'.join(lines)


def claims(text):
    positive, negative = [], []
    for line, prose in paragraphs(text):
        normalized = normalize(prose)
        negative.extend((line, m.group()) for m in NO.finditer(normalized))
        remaining = NO.sub(lambda m: ' ' * len(m.group()), normalized)
        positive.extend((line, m.group()) for m in YES.finditer(remaining))
    return positive, negative


def source_evidence(source):
    """Return evidence locations; imports never execute and pairs stay module-local."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    imports = {}
    shadows = set()
    mindee_imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
                mindee_imported |= alias.name == 'mindee' or alias.name.startswith('mindee.')
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ''
            mindee_imported |= module == 'mindee' or module.startswith('mindee.')
            for alias in node.names:
                imports[alias.asname or alias.name] = module + '.' + alias.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadows.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.With, ast.AsyncWith)):
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else
                [item.optional_vars for item in node.items if item.optional_vars])
            for target in targets:
                shadows.update(n.id for n in ast.walk(target)
                               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    def resolve(node):
        if isinstance(node, ast.Name):
            return imports.get(node.id, '') if node.id not in shadows else ''
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + '.' + node.attr if base and node.attr not in shadows else ''
        return ''

    def mindee_path(path):
        return path.replace('mindee.v1.', 'mindee.')

    def imported_root(node):
        while isinstance(node, ast.Attribute):
            node = node.value
        return mindee_path(resolve(node)) if isinstance(node, ast.Name) else ''

    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    evidence = []
    clients, parses = [], []
    for call in calls:
        func = call.func
        resolved = resolve(func)
        name = func.attr if isinstance(func, ast.Attribute) else resolved.rsplit('.', 1)[-1]
        if name in GENERIC_NAMES and name not in shadows:
            # Attribute calls may use any base; Name calls must resolve an import.
            if isinstance(func, ast.Attribute) or (isinstance(func, ast.Name) and resolved):
                evidence.append({'line': call.lineno, 'route': 'generic:' + name})
        path = mindee_path(resolved)
        if ((isinstance(func, ast.Name) and path == 'mindee.Client') or
                (isinstance(func, ast.Attribute) and func.attr == 'Client'
                 and imported_root(func) in ('mindee', 'mindee.v1') and path.endswith('.Client'))):
            clients.append(call.lineno)
        if isinstance(func, ast.Attribute) and func.attr == 'parse' and 'parse' not in shadows:
            products = ([call.args[0]] if call.args else []) + [
                kw.value for kw in call.keywords if kw.arg == 'product_class']
            for product in products:
                product_path = mindee_path(resolve(product))
                if isinstance(product, ast.Name):
                    valid = product_path in ('mindee.product.CropperV1', 'mindee.product.cropper.CropperV1')
                else:
                    valid = (isinstance(product, ast.Attribute) and product.attr == 'CropperV1'
                             and product_path.startswith('mindee.')
                             and imported_root(product) in ('mindee', 'mindee.v1', 'mindee.product',
                                                            'mindee.product.cropper',
                                                            'mindee.product.cropper.cropper_v1'))
                if valid:
                    parses.append(call.lineno)
    if mindee_imported and clients and parses:
        evidence.extend({'line': line, 'route': 'mindee:CropperV1'} for line in parses)
    return sorted(evidence, key=lambda item: (item['line'], item['route']))


def audit(repo='.', ignore=(), fail_on='high'):
    root = Path(repo)
    if not root.is_dir() or root.is_symlink():
        raise OSError('repository must be an existing, non-symlink directory')
    positives, negatives, production, tests = [], [], [], []
    prefixes = [p.replace('\\', '/').removeprefix('./').rstrip('/') for p in ignore]
    def ignored(relative):
        return any(relative.startswith(prefix) for prefix in prefixes)
    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink()
                         and not ignored((Path(directory) / d).relative_to(root).as_posix()))
        for filename in sorted(files):
            path = Path(directory) / filename
            relative = path.relative_to(root)
            name = relative.as_posix()
            if path.is_symlink() or ignored(name):
                continue
            parts = relative.parts
            is_doc = name == 'README.md' or (path.suffix == '.md' and 'docs' in parts[:-1])
            is_source = path.suffix == '.py' and not {'fixtures', 'docs', 'examples'}.intersection(parts[:-1])
            if not (is_doc or is_source):
                continue
            text = path.read_text(encoding='utf-8')
            if is_doc:
                yes, no = claims(text)
                positives.extend({'path': name, 'line': line, 'phrase': phrase} for line, phrase in yes)
                negatives.extend({'path': name, 'line': line, 'phrase': phrase} for line, phrase in no)
            if is_source:
                destination = tests if ('tests' in parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')) else production
                destination.extend(dict(item, path=name) for item in source_evidence(text))
    findings = []
    if positives and not production:
        findings.append({'rule': 'documented-document-cropping-claim-false',
                         'severity': 'MEDIUM' if tests else 'HIGH',
                         'message': 'Claim has only test evidence.' if tests else 'Claim has no production evidence.',
                         'locations': positives})
    if negatives and production:
        findings.append({'rule': 'documented-no-document-cropping-claim-false', 'severity': 'HIGH',
                         'message': 'Denial contradicts production evidence.', 'locations': negatives})
    failed = any(f['severity'] == 'HIGH' or fail_on == 'medium' for f in findings)
    return {'verdict': 'FAIL' if failed else 'PASS', 'findings': findings,
            'production_evidence': production, 'test_evidence': tests,
            'claims': positives, 'denials': negatives}
