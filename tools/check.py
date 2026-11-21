"""Checks every translation against the English source: run by GitHub Actions on each change.

  python tools/check.py

A translation file must be valid JSON, use only keys of the English source, keep the same placeholders
(%s, %d, %1$s, %%) and the same shape (a text, or a list with as many lines). Empty texts are allowed (not translated yet).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r'%(?:\d+\$)?[sd]|%%')


def signature(text):
    texts = text if isinstance(text, list) else [text]
    return sorted(m.group(0) for t in texts for m in PLACEHOLDER.finditer(t))


def check(source, data):
    if not isinstance(data, dict):
        return ['not a JSON object']
    out = []
    for key, value in data.items():
        if value in ('', [], None) or (isinstance(value, list) and not any(value)):
            continue
        if key not in source:
            out.append(f'{key}: not in the English source'); continue
        english = source[key]
        if isinstance(english, list):
            if not isinstance(value, list) or len(value) != len(english) or not all(isinstance(v, str) for v in value):
                out.append(f'{key}: expected a list of {len(english)} lines'); continue
        elif not isinstance(value, str):
            out.append(f'{key}: expected a text'); continue
        if signature(value) != signature(english):
            out.append(f'{key}: placeholders {signature(value)} instead of {signature(english)}')
    return out


def main():
    errors, files = [], 0
    for source_file in sorted((ROOT / 'source').glob('*/en_us.json')):
        part = source_file.parent.name
        source = json.loads(source_file.read_text(encoding='utf-8-sig'))
        for path in sorted((ROOT / 'translations' / part).glob('*.json')):
            files += 1
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
            except ValueError as e:
                errors.append(f'{part}/{path.name}: invalid JSON ({e})'); continue
            errors += [f'{part}/{path.name}: {p}' for p in check(source, data)]
    print('\n'.join(errors) or f'{files} translation files OK')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
