"""Kiểm tra route bảo vệ và hợp đồng form xác thực của giao diện."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from app.db import init_db

from app import create_app


class FrontendAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict('os.environ', {'DATABASE': str(Path(self.tmp.name) / 'test.db')})
        self.env.start()
        self.app = create_app('testing')
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_guest_redirect_preserves_target(self):
        for path in ('/cart?coupon=ABC', '/checkout', '/checkout/shipping', '/account/orders'):
            with self.subTest(path=path):
                result = self.client.get(path)
                self.assertEqual(result.status_code, 302)
                self.assertEqual(parse_qs(urlsplit(result.location).query)['next'], [path])

    def test_register_session_and_authenticated_pages(self):
        result = self.client.post('/api/auth/register', json={
            'full_name': 'Nguyễn Văn A', 'email': 'frontend@example.com',
            'password': 'Strongpass123', 'confirm_password': 'Strongpass123'
        })
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.client.get('/api/auth/me').json['user']['email'], 'frontend@example.com')
        self.assertEqual(self.client.get('/cart').status_code, 200)
        header = self.client.get('/').get_data(as_text=True).split('</header>', 1)[0]
        self.assertIn('data-auth-guest hidden', header)
        self.assertIn('data-auth-user  href="/account"', header)
        self.assertIn('title="Nguyễn Văn A"', header)
        self.assertIn('>Tài khoản</span>', header)
        self.assertEqual(self.client.get('/login?next=/cart').location, '/cart')
        self.assertEqual(self.client.get('/register?next=//evil.test').location, '/')
        csrf = self.client.get_cookie('csrf_token')
        self.client.post('/api/auth/logout', json={}, headers={'X-CSRF-Token': csrf.value})
        self.assertEqual(self.client.get('/account').status_code, 302)

class AuthMarkupTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app('testing').test_client()

    def test_forms_have_api_scripts_and_submit_controls(self):
        for page in ('login', 'register'):
            html = self.client.get('/' + page).get_data(as_text=True)
            self.assertIn('data-auth-form="' + page + '"', html)
            self.assertIn('type="submit"', html)
            self.assertIn('name="email"', html)
            self.assertIn('/static/js/core/api.js', html)
            self.assertIn('/static/js/core/auth.js', html)
        register = self.client.get('/register').get_data(as_text=True)
        self.assertIn('name="terms" checked required', register)
        self.assertIn('data-auth-switch href="/login"', register)
        self.assertIn('data-auth-switch href="/register"', self.client.get('/login').get_data(as_text=True))

    def test_header_has_login_but_no_registration_link(self):
        html = self.client.get('/').get_data(as_text=True)
        header = html.split('</header>', 1)[0]
        self.assertIn('href="/login"', header)
        self.assertNotIn('href="/register"', header)

class PageScriptTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app('testing').test_client()

    def test_page_scripts_are_loaded_only_where_needed(self):
        for page, path in (('/product', 'pages/product.js'),
                           ('/cart', 'pages/cart.js'),
                           ('/checkout', 'pages/checkout.js')):
            # Guest routes redirect; the fragment is present in the page template.
            from pathlib import Path
            template = Path(__file__).resolve().parents[1] / 'app' / 'templates'
            name = {'/product': 'store/product_detail.html', '/cart': 'store/cart.html',
                    '/checkout': 'checkout/checkout.html'}[page]
            self.assertIn("filename='js/" + path + "'", (template / name).read_text())
            self.assertTrue((template.parent / 'static' / 'js' / path).is_file())
        home = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('/static/js/pages/', home)
        self.assertIn('/static/js/core/api.js', home)
