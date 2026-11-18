import os
import re
import glob
import unittest
from app import app, db

class RepetitorDeepAudit(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_internal_template_links(self):
        """Check all static href and src links inside templates."""
        patterns = [
            re.compile(r'href=["\']([^"\'#]+)["\']'),
            re.compile(r'src=["\']([^"\'#]+)["\']')
        ]
        urls = set()
        for f in glob.glob('templates/*.html'):
            with open(f, 'r', encoding='utf-8') as fp:
                content = fp.read()
            for p in patterns:
                for u in p.findall(content):
                    if (not u.startswith('http') and 
                        not u.startswith('tel:') and 
                        not u.startswith('mailto:') and 
                        '{{' not in u):
                        urls.add(u)

        print("\nChecking internal template links:")
        for u in sorted(urls):
            # Test each URL with test client
            res = self.client.get(u, follow_redirects=True)
            print(f"  {u:25} -> {res.status_code}")
            self.assertEqual(res.status_code, 200, f"Broken link in template: {u}")

    def test_all_templates_render_cleanly(self):
        """Test rendering of all templates with mock context to catch Jinja undefined/filter bugs."""
        templates = glob.glob('templates/*.html')
        print(f"\nVerifying {len(templates)} templates syntax:")
        with app.test_request_context('/'):
            from flask import render_template
            for t_path in templates:
                t_name = os.path.basename(t_path)
                if t_name in ['base.html', 'karta.html']:
                    continue
                try:
                    # Provide realistic dummy context
                    dummy_tutor = {
                        'id': 1, 'ism': 'Test', 'fan': 'Mat', 'shahar': 'Toshkent',
                        'narx': 100000, 'telefon': '+998901234567', 'telegram': 'test',
                        'tavsif': 'Bio', 'rasm': None, 'bepul_dars': 1, 'korishlar': 5,
                        'reyting': '5.0', 'sharh_soni': 1, 'user_id': 1
                    }
                    html = render_template(
                        t_name,
                        t=dummy_tutor,
                        tutors=[dummy_tutor],
                        sharhlar=[],
                        users=[],
                        stat={'users': 1, 'tutors': 1, 'sharhlar': 1, 'elon': 1, 'korish': 5, 'sharh': 0, 'reyting': '5.0'},
                        limit=1,
                        yozgan=[],
                        fanlar=['Matematika'],
                        shaharlar=['Toshkent'],
                        tartiblar=['yangi', 'arzon', 'qimmat', 'reyting'],
                        tartib='yangi',
                        q='', fan='', shahar='',
                        xato='', xabar='',
                        mening=None,
                        adminlar={'admin'},
                        limit_yetdi=False
                    )
                    self.assertTrue(len(html) > 0)
                    print(f"  ✓ {t_name}")
                except Exception as e:
                    self.fail(f"Template {t_name} failed to render: {e}")

if __name__ == '__main__':
    unittest.main()
