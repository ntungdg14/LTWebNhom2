"""JWT cookie, CSRF, revocation and session migration regression tests."""
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from app import create_app
from app.common.jwt_auth import COOKIE, issue
from app.db import init_db, get_db


class JWTAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app('testing')
        self.app.config['DATABASE'] = os.path.join(self.tmp.name, 'auth.db')
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()
        self.client.post('/api/auth/register', json={
            'full_name': 'JWT Customer', 'email': 'jwt@example.com', 'password': 'SecurePass123'
        })

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self):
        return {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}

    def test_cookie_and_reload_and_logout(self):
        cookie = self.client.get_cookie(COOKIE)
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.value.count('.'), 2)
        self.assertIsNotNone(self.client.get('/api/auth/me').json['user'])
        token = cookie.value
        self.assertEqual(self.client.post('/api/auth/logout', json={}, headers=self.csrf()).status_code, 200)
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])
        self.client.set_cookie(COOKIE, token)
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])  # revoked JWT cannot be replayed

    def test_invalid_signature_expiry_and_old_flask_session(self):
        cookie = self.client.get_cookie(COOKIE).value
        self.client.set_cookie(COOKIE, cookie[:-1] + ('A' if cookie[-1] != 'A' else 'B'))
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])
        with self.app.app_context():
            user = get_db().execute('SELECT * FROM users WHERE email = ?', ('jwt@example.com',)).fetchone()
            with patch('app.common.jwt_auth.time.time', return_value=100):
                expired, _ = issue(user)
        self.client.set_cookie(COOKIE, expired)
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])
        self.client.delete_cookie(COOKIE)
        with self.client.session_transaction() as session:
            session['uid'], session['sv'] = 1, 0
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])

    def test_csrf_rejects_missing_and_wrong_header(self):
        self.assertEqual(self.client.post('/api/account/logout-all', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/account/logout-all', json={}, headers={'X-CSRF-Token': 'wrong'}).status_code, 403)
        self.assertIsNotNone(self.client.get('/api/auth/me').json['user'])
        self.assertEqual(self.client.post('/api/account/logout-all', json={}, headers=self.csrf()).status_code, 200)
        self.assertIsNone(self.client.get('/api/auth/me').json['user'])

    def test_cross_site_origin_denied(self):
        result = self.client.post('/api/auth/login', json={'email': 'jwt@example.com', 'password': 'SecurePass123'},
                                  headers={'Origin': 'https://attacker.example'})
        self.assertEqual(result.status_code, 403)
