"""Exercise the Pages staging step: agent entry points must survive deployment."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import re
import textwrap

ROOT = Path(os.environ.get('ANOMALY_SITE_ROOT', Path(__file__).resolve().parents[1]))


class SitePublishTest(unittest.TestCase):
    def test_public_agent_entry_points_are_staged(self):
        workflow = (ROOT / '.github/workflows/pages.yml').read_text()
        match = re.search(r'(?m)^      - name: Stage site\n        run: \|\n((?:          .*\n)+)', workflow)
        self.assertIsNotNone(match, 'Pages workflow must have an executable Stage site step')
        stage = textwrap.dedent(match.group(1))
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            for name in ('index.html', 'CNAME', 'llms.txt', 'docs', 'shared'):
                source = ROOT / name
                if source.is_dir():
                    shutil.copytree(source, work / name)
                elif source.exists():
                    shutil.copy2(source, work / name)
            subprocess.run(['bash', '-eu', '-c', stage], cwd=work, check=True, capture_output=True)
            for public_path in ('index.html', 'docs/context.json', 'llms.txt', 'shared/property-signal.css', 'shared/property-signal.js'):
                with self.subTest(path=public_path):
                    self.assertTrue((work / '_site' / public_path).is_file(), f'Published site is missing /{public_path}')


if __name__ == '__main__':
    unittest.main()
