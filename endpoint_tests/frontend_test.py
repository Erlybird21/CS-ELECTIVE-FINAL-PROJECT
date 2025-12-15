import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

class FrontendTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_index(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Cost Tracker', response.data)

    def test_static_files(self):
        response = self.client.get('/static/js/script.js')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/static/css/style.css')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
