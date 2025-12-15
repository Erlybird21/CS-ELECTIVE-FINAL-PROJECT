
import os
import unittest
import sys

# Add parent directory to path so we can import app and config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from config import TestConfig
from endpoint_tests.data_create import ensure_schema_and_seed


def _mysql_env_ready() -> bool:
    return bool(os.getenv("MYSQL_DB"))


class ExpenseApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _mysql_env_ready():
            # If env vars are not set, we might skip or try to use defaults if config allows
            # For this environment, we assume they are set or config has defaults
            pass
        ensure_schema_and_seed(20)

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.token = self._login()

    def _login(self) -> str:
        resp = self.client.post(
            "/auth/login",
            json={"username": self.app.config["ADMIN_USERNAME"], "password": self.app.config["ADMIN_PASSWORD"]},
        )
        if resp.status_code != 200:
             raise Exception(f"Login failed: {resp.data}")
        data = resp.get_json()
        return data["access_token"]

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # === AUTH TESTS ===
    def test_requires_auth(self):
        """Test that /api/expenses requires JWT."""
        resp = self.client.get("/api/expenses")
        self.assertEqual(resp.status_code, 401)

    def test_login_success(self):
        """Test login endpoint."""
        resp = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")

    def test_login_failure(self):
        """Test login with wrong password."""
        resp = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        self.assertEqual(resp.status_code, 401)

    # === LIST TESTS ===
    def test_list_expenses_json(self):
        """Test listing expenses in JSON format."""
        resp = self.client.get("/api/expenses", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)
        self.assertIn("count", data)
        self.assertGreaterEqual(data["count"], 20)

    def test_list_expenses_xml(self):
        """Test listing expenses in XML format."""
        resp = self.client.get("/api/expenses?format=xml", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/xml"))
        self.assertIn(b"<response>", resp.data)

    # === GET SINGLE EXPENSE ===
    def test_get_expense_exists(self):
        """Test getting a specific expense."""
        # Get ID from list first
        list_resp = self.client.get("/api/expenses", headers=self._auth_headers())
        first_id = list_resp.get_json()["data"][0]["expense_id"]
        
        resp = self.client.get(f"/api/expenses/{first_id}", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)

    def test_get_expense_not_found(self):
        """Test getting a non-existent expense."""
        resp = self.client.get("/api/expenses/999999", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 404)

    # === CREATE EXPENSE ===
    def test_create_expense_success(self):
        """Test creating a new expense."""
        resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": 500.00,
                "category_name": "Food",
                "vendor_name": "Jollibee",
                "payment_method_name": "Cash",
                "description": "Christmas dinner",
                "qty": 4,
                "unit_price": 125.00,
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("data", data)
        self.assertIn("expense_id", data["data"])

    def test_create_expense_missing_required_field(self):
        """Test creating expense with missing required field."""
        resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": 500.00,
                # missing category_name, vendor_name, payment_method_name
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], "validation_error")

    def test_create_expense_invalid_date(self):
        """Test creating expense with invalid date format."""
        resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "25-12-2025",  # wrong format
                "amount": 500.00,
                "category_name": "Food",
                "vendor_name": "Jollibee",
                "payment_method_name": "Cash",
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_expense_invalid_amount(self):
        """Test creating expense with negative amount."""
        resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": -100.00,
                "category_name": "Food",
                "vendor_name": "Jollibee",
                "payment_method_name": "Cash",
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_expense_nonexistent_category(self):
        """Test creating expense with non-existent category."""
        resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": 500.00,
                "category_name": "NonExistentCategory",
                "vendor_name": "Jollibee",
                "payment_method_name": "Cash",
            },
        )
        self.assertEqual(resp.status_code, 400)

    # === UPDATE EXPENSE ===
    def test_update_expense_success(self):
        """Test updating an expense."""
        # First create an expense
        create_resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-21",
                "amount": 200.00,
                "category_name": "Food",
                "vendor_name": "Starbucks",
                "payment_method_name": "Cash",
                "description": "Initial description",
            },
        )
        expense_id = create_resp.get_json()["data"]["expense_id"]

        # Update it
        update_resp = self.client.put(
            f"/api/expenses/{expense_id}",
            headers=self._auth_headers(),
            json={"amount": 350.00, "description": "Updated description"},
        )
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.get_json()["data"]
        self.assertAlmostEqual(float(updated["amount"]), 350.00, places=2)

    def test_update_expense_not_found(self):
        """Test updating non-existent expense."""
        resp = self.client.put(
            "/api/expenses/999999",
            headers=self._auth_headers(),
            json={"amount": 999.00},
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_expense_partial(self):
        """Test partial update (only amount)."""
        create_resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-22",
                "amount": 100.00,
                "category_name": "Transportation",
                "vendor_name": "Grab",
                "payment_method_name": "GCash",
            },
        )
        expense_id = create_resp.get_json()["data"]["expense_id"]

        update_resp = self.client.put(
            f"/api/expenses/{expense_id}",
            headers=self._auth_headers(),
            json={"amount": 200.00},
        )
        self.assertEqual(update_resp.status_code, 200)

    # === DELETE EXPENSE ===
    def test_delete_expense_success(self):
        """Test deleting an expense."""
        create_resp = self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-23",
                "amount": 300.00,
                "category_name": "Entertainment",
                "vendor_name": "Netflix",
                "payment_method_name": "Credit Card",
            },
        )
        expense_id = create_resp.get_json()["data"]["expense_id"]

        del_resp = self.client.delete(f"/api/expenses/{expense_id}", headers=self._auth_headers())
        self.assertEqual(del_resp.status_code, 204)

        # Verify it's gone
        get_resp = self.client.get(f"/api/expenses/{expense_id}", headers=self._auth_headers())
        self.assertEqual(get_resp.status_code, 404)

    def test_delete_expense_not_found(self):
        """Test deleting non-existent expense."""
        resp = self.client.delete("/api/expenses/999999", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 404)

    # === SEARCH ENDPOINT ===
    def test_search_by_category(self):
        """Test searching by category."""
        # Ensure we have at least one 'Food' expense
        self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": 500.00,
                "category_name": "Food",
                "vendor_name": "Jollibee",
                "payment_method_name": "Cash",
            },
        )
        
        resp = self.client.get(
            "/api/expenses/search?category=Food",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)
        self.assertIn("count", data)
        self.assertGreater(data["count"], 0)

    def test_search_by_vendor(self):
        """Test searching by vendor."""
        # Ensure we have at least one 'Starbucks' expense
        self.client.post(
            "/api/expenses",
            headers=self._auth_headers(),
            json={
                "expense_date": "2025-12-25",
                "amount": 500.00,
                "category_name": "Food",
                "vendor_name": "Starbucks",
                "payment_method_name": "Cash",
            },
        )

        resp = self.client.get(
            "/api/expenses/search?vendor=Starbucks",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)
        self.assertGreater(data["count"], 0)

    def test_search_by_amount_range(self):
        """Test searching by amount range."""
        resp = self.client.get(
            "/api/expenses/search?min_amount=100&max_amount=300",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)
        for expense in data["data"]:
            self.assertGreaterEqual(float(expense["amount"]), 100)
            self.assertLessEqual(float(expense["amount"]), 300)

    def test_search_by_date_range(self):
        """Test searching by date range."""
        resp = self.client.get(
            "/api/expenses/search?start_date=2025-12-01&end_date=2025-12-10",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("data", data)

    def test_search_no_params(self):
        """Test search without parameters."""
        resp = self.client.get("/api/expenses/search", headers=self._auth_headers())
        self.assertEqual(resp.status_code, 400)

    def test_search_xml_format(self):
        """Test search results in XML format."""
        resp = self.client.get(
            "/api/expenses/search?category=Food&format=xml",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/xml"))

    # === FORMAT TESTS ===
    def test_format_xml_default_json(self):
        """Test that default format is JSON."""
        resp = self.client.get("/api/expenses", headers=self._auth_headers())
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/json"))

    def test_format_xml_explicit(self):
        """Test explicit XML format."""
        resp = self.client.get("/api/expenses?format=xml", headers=self._auth_headers())
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/xml"))

    def test_format_case_insensitive(self):
        """Test that format parameter is case-insensitive."""
        resp = self.client.get("/api/expenses?format=XML", headers=self._auth_headers())
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/xml"))


if __name__ == "__main__":
    unittest.main()

