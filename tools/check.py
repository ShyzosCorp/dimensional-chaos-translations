"""Checks the translations, and what a pull request changes in them, before anyone merges it.

  python tools/check.py                       every file on its own (as before)
  python tools/check.py --base origin/main    also compares with the base branch (pull requests)

On its own, a translation file must:
  - be valid JSON, with no key written twice;
  - have a Minecraft language file name (fr_fr.json, pt_br.json...) in the right folder;
  - use only keys of the English source;
  - keep the same placeholders (%s, %d, %1$s, %%: French may reorder %s %s into %2$s ... %1$s);
  - keep the same Minecraft formatting codes (section sign + 0-9, a-f, k-o, r), all of them valid;
  - keep the same shape (a text, or a list with as many lines).
Empty texts are allowed: not translated yet, the game shows the English.

Against the base branch, a pull request must not:
  - delete or rename a translation file, a translations folder or an English source;
  - change the English sources, or a quest identifier (key) in them;
  - change the tooling (tools/, .github/, crowdin.yml, CODEOWNERS), this script included;
  - add files anywhere else than translations/<part>/<language>.json;
  - remove a translation, empty it, or replace it with the English text.
Every file of the base and of the pull request is compared, so a file that disappears is a loss, not a
file left unchecked. The comparison fails safe: if the base cannot be read, or any git command fails,
the check fails instead of treating the missing answer as "nothing to compare".

A wanted change passes when the owner adds the label named in ALLOW_LABELS. The workflow passes only the
labels the owner applied himself (L10N_LABELS), and the name of the pull request's branch (L10N_BRANCH).
On a Crowdin branch (l10n_*), the source and tooling labels never count: Crowdin only brings translations.
The workflow runs this script as it is on the base branch, so a pull request cannot loosen its own check.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]    # or --root (the workflow runs the base's copy)
PLACEHOLDER = re.compile(r'%(?:(\d+)\$)?[sd]|%%')
FORMAT = re.compile('§(.)', re.S)
VALID_FORMAT = set('0123456789abcdefklmnor')
LANG_FILE = re.compile(r'[a-z]{2,3}_[a-z0-9]{2,4}\.json')
ALLOWED_PATH = re.compile(r'translations/(mod|quests)/[a-z]{2,3}_[a-z0-9]{2,4}\.json|README\.md')
ALLOW_LABELS = {
    'source': 'l10n:source-change',     # English sources or quest keys changed on purpose
    'removal': 'l10n:allow-removal',    # translations removed or reverted to English on purpose
    'tooling': 'l10n:tooling-change',   # this script, the workflow, crowdin.yml changed on purpose
}
TOOLING = ('tools/', '.github/', 'crowdin.yml', 'CODEOWNERS')
CROWDIN_BRANCH = 'l10n_'
SOURCE_FILE = re.compile(r'source/([a-z0-9_-]+)/en_us\.json')
TRANSLATION_FILE = re.compile(r'translations/([a-z0-9_-]+)/([^/]+)')
# Minecraft 1.21.1 language codes (assets/minecraft/lang); any other file name is never loaded by the game.
MINECRAFT_LANGS = set('''af_za ar_sa ast_es az_az ba_ru bar be_by be_latn bg_bg br_fr brb bs_ba ca_es cs_cz cy_gb
da_dk de_at de_ch de_de el_gr en_au en_ca en_gb en_nz en_pt en_ud en_us enp enws eo_uy es_ar es_cl es_ec es_es es_mx
es_uy es_ve esan et_ee eu_es fa_ir fi_fi fil_ph fo_fo fr_ca fr_fr fra_de fur_it fy_nl ga_ie gd_gb gl_es haw_us he_il
hi_in hn_no hr_hr hu_hu hy_am id_id ig_ng io_en is_is isv it_it ja_jp jbo_en ka_ge kk_kz kn_in ko_kr ksh kw_gb ky_kg
la_la lb_lu li_li lmo lo_la lol_us lt_lt lv_lv lzh mk_mk mn_mn ms_my mt_mt nah nds_de nl_be nl_nl nn_no no_no oc_fr
ovd pl_pl pls pt_br pt_pt qya_aa ro_ro rpr ru_ru ry_ua sah_sah se_no sk_sk sl_si so_so sq_al sr_cs sr_sp sv_se sxu
szl ta_in th_th tl_ph tlh_aa tok tr_tr tt_ru tzo_mx uk_ua val_es vec_it vi_vn vp_vl yi_de yo_ng zh_cn zh_hk zh_tw
zlm_arab'''.split())


def placeholders(text):
    """Arguments as %N$x, bare %s numbered by position, sorted: reordering is fine, dropping one is not."""
    out, n = [], 1
    for t in (text if isinstance(text, list) else [text]):
        for m in PLACEHOLDER.finditer(t):
            if m.group(0) == '%%': out.append('%%'); continue
            out.append(f'%{m.group(1) or n}${m.group(0)[-1]}')
            if not m.group(1): n += 1
    return sorted(out)


def formats(text):
    return sorted(c.lower() for t in (text if isinstance(text, list) else [text]) for c in FORMAT.findall(t))


def no_duplicates(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen: raise ValueError(f'key written twice: {k}')
        seen[k] = v
    return seen


def parse(text):
    return json.loads(text, object_pairs_hook=no_duplicates)


def translated(value):
    return value not in ('', [], None) and not (isinstance(value, list) and not any(value))


def check_file(source, data):
    if not isinstance(data, dict):
        return ['not a JSON object']
    out = []
    for key, value in data.items():
        if not translated(value): continue
        if key not in source: out.append(f'{key}: not in the English source'); continue
        english = source[key]
        if isinstance(english, list):
            if not isinstance(value, list) or len(value) != len(english) or not all(isinstance(v, str) for v in value):
                out.append(f'{key}: expected a list of {len(english)} lines'); continue
        elif not isinstance(value, str):
            out.append(f'{key}: expected a text'); continue
        if placeholders(value) != placeholders(english):
            out.append(f'{key}: placeholders {placeholders(value)} instead of {placeholders(english)}')
        bad = sorted({c for c in formats(value) if c not in VALID_FORMAT})
        if bad: out.append(f'{key}: invalid formatting code(s) {bad}')
        elif formats(value) != formats(english):
            out.append(f'{key}: formatting codes {formats(value)} instead of {formats(english)}')
    return out


class GitError(Exception):
    pass


def git(*args):
    """Runs git; any failure raises, so no answer is ever read as "nothing there"."""
    try:
        run = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, encoding='utf-8')
    except OSError as e:
        raise GitError(f'git {" ".join(args)}: {e}')
    if run.returncode != 0:
        raise GitError(f'git {" ".join(args)} exited {run.returncode}: {run.stderr.strip()[:300]}')
    return run.stdout


def at_base(base, path):
    return parse(git('show', f'{base}:{path}').lstrip('﻿'))


def in_tree():
    """Files of the pull request (the checked-out tree) under source/ and translations/."""
    return {p.relative_to(ROOT).as_posix() for top in ('source', 'translations')
            for p in (ROOT / top).rglob('*') if p.is_file()}


def read_head(rel, errors):
    try:
        data = parse((ROOT / rel).read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeDecodeError):
        errors.append(f'{rel}: unreadable, so every translation it had counts as lost')
        return {}
    return data if isinstance(data, dict) else {}


def compare(base, labels, branch=''):
    if branch.startswith(CROWDIN_BRANCH):
        labels = labels - {ALLOW_LABELS['source'], ALLOW_LABELS['tooling']}
    git('rev-parse', '--verify', '--quiet', f'{base}^{{commit}}')
    git('merge-base', base, 'HEAD')    # a shallow clone has none: fail rather than diff against nothing
    errors = []
    changed = {p for p in git('diff', '--name-only', '--no-renames', f'{base}...HEAD').splitlines() if p}
    base_files = {p for p in git('ls-tree', '-r', '--name-only', base, '--', 'source', 'translations').splitlines() if p}
    head_files = in_tree()

    for path in sorted(changed):
        if path.startswith(TOOLING):
            if ALLOW_LABELS['tooling'] not in labels:
                errors.append(f'{path}: tooling changed (label {ALLOW_LABELS["tooling"]} by the owner if wanted; '
                              f'never on a Crowdin branch)')
        elif path.startswith('source/'):
            if ALLOW_LABELS['source'] not in labels:
                errors.append(f'{path}: English source changed (label {ALLOW_LABELS["source"]} if wanted)')
        elif not ALLOWED_PATH.fullmatch(path) and not path.startswith(('glossary/', 'docs/')):
            errors.append(f'{path}: file outside translations/<part>/<language>.json')

    parts = sorted({m.group(1) for p in base_files | head_files for m in [SOURCE_FILE.fullmatch(p)] if m}
                   | {m.group(1) for p in base_files for m in [TRANSLATION_FILE.fullmatch(p)] if m})
    for part in parts:
        src = f'source/{part}/en_us.json'
        old_source = at_base(base, src) if src in base_files else {}
        if src in base_files and src not in head_files:
            errors.append(f'{src}: English source deleted')
            source = {}
        elif src in head_files:
            source = read_head(src, errors)
        else:
            source = {}
        gone = sorted(set(old_source) - set(source))
        if gone and source and ALLOW_LABELS['source'] not in labels:
            errors.append(f'{src}: {len(gone)} key(s) removed or renamed, e.g. {gone[:3]}')
        reference = source or old_source
        prefix = f'translations/{part}/'
        names = sorted(p for p in base_files | head_files if p.startswith(prefix) and p.endswith('.json'))
        if any(p in base_files for p in names) and not any(p in head_files for p in names):
            errors.append(f'{prefix}: the whole translations folder is gone')
        for rel in names:
            deleted = rel in base_files and rel not in head_files
            if rel not in changed and not deleted:
                continue
            before = at_base(base, rel) if rel in base_files else {}
            after = {} if deleted else read_head(rel, errors)
            lost = [k for k, v in before.items()
                    if translated(v) and v != old_source.get(k) and k in reference
                    and (not translated(after.get(k)) or after.get(k) == reference.get(k))]
            english = [k for k, v in after.items() if translated(v) and v == source.get(k) and before.get(k) != v]
            if lost and ALLOW_LABELS['removal'] not in labels:
                what = 'file deleted or renamed' if deleted else 'translation(s) removed, emptied or replaced by English'
                errors.append(f'{rel}: {what}: {len(lost)} translation(s) lost, e.g. {lost[:3]} '
                              f'(label {ALLOW_LABELS["removal"]} by the owner if wanted)')
            elif len(english) > max(10, len(source) // 10) and ALLOW_LABELS['removal'] not in labels:
                errors.append(f'{rel}: {len(english)} texts newly identical to the English: an export of untranslated strings?')
    return errors


def main():
    global ROOT
    if '--root' in sys.argv:
        ROOT = Path(sys.argv[sys.argv.index('--root') + 1]).resolve()
    errors, files = [], 0
    for source_file in sorted((ROOT / 'source').glob('*/en_us.json')):
        part = source_file.parent.name
        try:
            source = parse(source_file.read_text(encoding='utf-8-sig'))
        except ValueError as e:
            errors.append(f'source/{part}/en_us.json: invalid JSON ({e})'); continue
        for path in sorted((ROOT / 'translations' / part).glob('*')):
            files += 1
            name = f'{part}/{path.name}'
            if not LANG_FILE.fullmatch(path.name) or path.stem not in MINECRAFT_LANGS or path.stem == 'en_us':
                errors.append(f'{name}: not a Minecraft language file name'); continue
            try:
                data = parse(path.read_text(encoding='utf-8-sig'))
            except ValueError as e:
                errors.append(f'{name}: invalid JSON ({e})'); continue
            errors += [f'{name}: {p}' for p in check_file(source, data)]
    for folder in sorted(p for p in (ROOT / 'translations').glob('*') if p.is_dir()):
        if not (ROOT / 'source' / folder.name / 'en_us.json').is_file():
            errors.append(f'translations/{folder.name}/: no English source (source/{folder.name}/en_us.json), so nothing in it is checked')
    if files == 0:
        errors.append('no translation file found: wrong folder, or everything deleted')
    if '--base' in sys.argv:
        labels = set(filter(None, os.environ.get('L10N_LABELS', '').split(',')))
        try:
            errors += compare(sys.argv[sys.argv.index('--base') + 1], labels, os.environ.get('L10N_BRANCH', ''))
        except (GitError, ValueError, IndexError) as e:
            errors.append(f'cannot compare with the base, so the check fails: {e}')
    print('\n'.join(errors) or f'{files} translation files OK')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
