"""Tests of tools/check.py on real, throw-away git repositories.

  python tests/test_check.py        (from the proposed/ folder; needs git and Python 3.10+)

Each test builds a small translations repository on main, makes a pull request branch, and runs the
check exactly as the workflow does: the script taken from the BASE commit, --root, --base, and the
L10N_LABELS / L10N_BRANCH variables.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / 'tools' / 'check.py'

MOD_EN = {'item.dc.key': 'Dimensional Key', 'gui.dc.hello': 'Hello %s', 'gui.dc.rank': '§6Rank§r %s'}
MOD_FR = {'item.dc.key': 'Clé dimensionnelle', 'gui.dc.hello': 'Bonjour %s', 'gui.dc.rank': '§6Grade§r %s'}
MOD_ZH = {'item.dc.key': '维度钥匙', 'gui.dc.hello': '你好 %s'}
QUEST_EN = {'quest.dc/start.0.title': 'First steps', 'quest.dc/start.0.desc': 'Break the block'}
QUEST_FR = {'quest.dc/start.0.title': 'Premiers pas', 'quest.dc/start.0.desc': 'Casse le bloc'}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class Repo:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'test')
        self.git('config', 'core.autocrlf', 'false')
        (root / 'tools').mkdir()
        shutil.copy(CHECK, root / 'tools' / 'check.py')
        dump(root / 'source/mod/en_us.json', MOD_EN)
        dump(root / 'source/quests/en_us.json', QUEST_EN)
        dump(root / 'translations/mod/fr_fr.json', MOD_FR)
        dump(root / 'translations/mod/zh_cn.json', MOD_ZH)
        dump(root / 'translations/quests/fr_fr.json', QUEST_FR)
        self.commit('base')
        self.git('checkout', '-q', '-b', 'pr')

    def git(self, *args, check=True):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=check)

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '--allow-empty', '-m', message)

    def run(self, base='main', labels=(), branch='feature', script_from='main'):
        """The workflow's way: the base's own script judges the pull request."""
        script = self.root.parent / f'check-{script_from}.py'
        shown = self.git('show', f'{script_from}:tools/check.py', check=False)
        if shown.returncode != 0:
            return 1, 'no tools/check.py at the base'
        script.write_text(shown.stdout, encoding='utf-8')
        env = dict(os.environ, L10N_LABELS=','.join(labels), L10N_BRANCH=branch, PYTHONIOENCODING='utf-8')
        run = subprocess.run([sys.executable, str(script), '--root', str(self.root), '--base', base],
                             capture_output=True, text=True, encoding='utf-8', env=env, cwd=self.root)
        return run.returncode, run.stdout + run.stderr


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(Path(self.tmp.name) / 'repo')
        self.r = self.repo.root

    def tearDown(self):
        self.tmp.cleanup()

    def assertPasses(self, **kw):
        code, out = self.repo.run(**kw)
        self.assertEqual(code, 0, out)

    def assertFails(self, needle, **kw):
        code, out = self.repo.run(**kw)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)
        return out

    # ------------------------------------------------------------ what must pass
    def test_unchanged_branch_passes(self):
        self.assertPasses()

    def test_new_translation_passes(self):
        dump(self.r / 'translations/mod/zh_cn.json', dict(MOD_ZH, **{'gui.dc.rank': '§6等级§r %s'}))
        self.repo.commit('zh')
        self.assertPasses(branch='l10n_main')

    def test_new_partial_language_passes(self):
        dump(self.r / 'translations/mod/pl_pl.json', {'item.dc.key': 'Klucz wymiarowy'})
        self.repo.commit('pl partial')
        self.assertPasses(branch='l10n_main')

    def test_owner_label_allows_a_wanted_removal(self):
        (self.r / 'translations/mod/zh_cn.json').unlink()
        self.repo.commit('drop zh on purpose')
        self.assertPasses(labels=['l10n:allow-removal'])

    def test_owner_label_allows_tooling_on_an_owner_branch(self):
        with open(self.r / 'tools/check.py', 'a', encoding='utf-8') as f:
            f.write('\n# comment\n')
        self.repo.commit('tooling')
        self.assertPasses(labels=['l10n:tooling-change'], branch='owner/tooling')

    # ------------------------------------------------------------ deletions and renames
    def test_deleting_a_language_fails(self):
        # The case found in review: the old script said "0 translation files OK" and exited 0.
        (self.r / 'translations/mod/fr_fr.json').unlink()
        self.repo.commit('delete fr')
        self.assertFails('translations/mod/fr_fr.json: file deleted or renamed: 3 translation(s) lost')

    def test_deleting_every_language_fails(self):
        shutil.rmtree(self.r / 'translations')
        self.repo.commit('delete all')
        out = self.assertFails('the whole translations folder is gone')
        self.assertIn('no translation file found', out)

    def test_deleting_a_translations_folder_fails(self):
        shutil.rmtree(self.r / 'translations/quests')
        self.repo.commit('delete quests')
        self.assertFails('translations/quests/: the whole translations folder is gone')

    def test_deleting_a_source_fails(self):
        (self.r / 'source/quests/en_us.json').unlink()
        self.repo.commit('delete source')
        out = self.assertFails('source/quests/en_us.json: English source deleted')
        self.assertIn('translations/quests/: no English source', out)  # its translations would go unchecked

    def test_deleting_a_source_fails_even_with_the_source_label_on_crowdin(self):
        (self.r / 'source/quests/en_us.json').unlink()
        self.repo.commit('delete source')
        self.assertFails('English source', labels=['l10n:source-change'], branch='l10n_main')

    def test_accidental_rename_fails(self):
        (self.r / 'translations/mod/fr_fr.json').rename(self.r / 'translations/mod/fr_ca.json')
        self.repo.commit('rename')
        self.assertFails('translations/mod/fr_fr.json: file deleted or renamed')

    def test_rename_to_an_invalid_name_fails(self):
        (self.r / 'translations/mod/fr_fr.json').rename(self.r / 'translations/mod/fr-fr.json')
        self.repo.commit('rename')
        out = self.assertFails('not a Minecraft language file name')
        self.assertIn('fr_fr.json: file deleted or renamed', out)

    # ------------------------------------------------------------ empty and partial content
    def test_emptied_object_fails(self):
        dump(self.r / 'translations/mod/fr_fr.json', {})
        self.repo.commit('empty object')
        self.assertFails('removed, emptied or replaced by English: 3 translation(s) lost')

    def test_zero_byte_file_fails(self):
        (self.r / 'translations/mod/fr_fr.json').write_bytes(b'')
        self.repo.commit('zero bytes')
        out = self.assertFails('invalid JSON')
        self.assertIn('unreadable, so every translation it had counts as lost', out)

    def test_emptied_texts_fail(self):
        dump(self.r / 'translations/mod/fr_fr.json', {k: '' for k in MOD_FR})
        self.repo.commit('empty texts')
        self.assertFails('3 translation(s) lost')

    def test_existing_language_made_partial_fails(self):
        dump(self.r / 'translations/mod/fr_fr.json', {'item.dc.key': MOD_FR['item.dc.key']})
        self.repo.commit('partial fr')
        self.assertFails('2 translation(s) lost')

    def test_replaced_by_english_fails(self):
        # What Crowdin PRs #1 and #2 did: untranslated strings exported as English.
        dump(self.r / 'translations/mod/fr_fr.json', dict(MOD_FR, **{'item.dc.key': MOD_EN['item.dc.key']}))
        self.repo.commit('english')
        self.assertFails('1 translation(s) lost')

    # ------------------------------------------------------------ the check cannot be loosened
    def test_crowdin_pr_editing_the_script_fails(self):
        script = self.r / 'tools/check.py'
        script.write_text('import sys\nprint("all good")\nsys.exit(0)\n', encoding='utf-8')
        (self.r / 'translations/mod/fr_fr.json').unlink()
        self.repo.commit('loosen the check and delete fr')
        out = self.assertFails('tools/check.py: tooling changed', branch='l10n_main')
        self.assertIn('fr_fr.json: file deleted or renamed', out)
        # ...and the tooling label does not count on a Crowdin branch
        self.assertFails('tooling changed', labels=['l10n:tooling-change'], branch='l10n_main')
        # the pull request's own copy would have passed: this is why the base's copy is the judge
        code, _ = self.repo.run(script_from='pr')
        self.assertEqual(code, 0)

    def test_editing_the_workflow_or_crowdin_config_fails(self):
        dump(self.r / '.github/workflows/check.json', {})
        (self.r / 'crowdin.yml').write_text('skip_untranslated_strings: false\n', encoding='utf-8')
        self.repo.commit('workflow and config')
        out = self.assertFails('.github/workflows/check.json: tooling changed')
        self.assertIn('crowdin.yml: tooling changed', out)

    def test_source_change_needs_the_label_and_never_on_crowdin(self):
        dump(self.r / 'source/mod/en_us.json', dict(MOD_EN, **{'gui.dc.new': 'New'}))
        self.repo.commit('source')
        self.assertFails('English source changed')
        self.assertFails('English source changed', labels=['l10n:source-change'], branch='l10n_main')
        self.assertPasses(labels=['l10n:source-change'], branch='owner/source')

    # ------------------------------------------------------------ git failures fail safe
    def test_unknown_base_fails(self):
        self.assertFails('cannot compare with the base, so the check fails', base='no-such-branch')

    def test_unrelated_base_fails(self):
        self.repo.git('checkout', '-q', '--orphan', 'other')
        self.repo.commit('unrelated')
        self.repo.git('checkout', '-q', 'pr')
        self.assertFails('cannot compare with the base', base='other')

    def test_git_failing_during_the_comparison_fails(self):
        # The base's fr_fr.json object is missing: "git show" fails half way through the comparison.
        dump(self.r / 'translations/mod/fr_fr.json', dict(MOD_FR, **{'item.dc.key': 'Clé'}))
        self.repo.commit('edit fr')
        blob = self.repo.git('rev-parse', 'main:translations/mod/fr_fr.json').stdout.strip()
        obj = self.r / '.git' / 'objects' / blob[:2] / blob[2:]
        script = self.r.parent / 'check-main.py'
        script.write_text(self.repo.git('show', 'main:tools/check.py').stdout, encoding='utf-8')
        os.chmod(obj, 0o644)
        obj.unlink()
        env = dict(os.environ, L10N_LABELS='', L10N_BRANCH='feature', PYTHONIOENCODING='utf-8')
        run = subprocess.run([sys.executable, str(script), '--root', str(self.r), '--base', 'main'],
                             capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn('cannot compare with the base, so the check fails', run.stdout)

    def test_base_without_the_script_fails(self):
        code, out = self.repo.run(script_from='no-such-ref')
        self.assertEqual(code, 1, out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
