from __future__ import annotations

import datetime as dt
import decimal
import unittest
import io
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import jwt
from dicttoxml import dicttoxml
from flask import Flask, Response, jsonify, make_response, request, render_template
from flask.json.provider import DefaultJSONProvider
from flask_mysqldb import MySQL

from config import Config


mysql = MySQL()


def _wants_xml() -> bool:
    fmt = (request.args.get("format") or "").strip().lower()
    return fmt == "xml"


def api_response(payload: Any = None, *, status: int = 200, headers: Optional[Dict[str, str]] = None) -> Response:
    headers = headers or {}

    if status == 204:
        resp = make_response("", 204)
        for k, v in headers.items():
            resp.headers[k] = v
        return resp

    if _wants_xml():
        if payload is None:
            payload = {"result": None}
        elif not isinstance(payload, (dict, list)):
            payload = {"result": payload}
        xml_bytes = dicttoxml(payload, custom_root="response", attr_type=False)
        resp = make_response(xml_bytes, status)
        resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    else:
        resp = make_response(jsonify(payload), status)
        resp.headers["Content-Type"] = "application/json"

    for k, v in headers.items():
        resp.headers[k] = v
    return resp


def api_error(message: str, *, status: int = 400, code: str = "bad_request", details: Any = None) -> Response:
    payload: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return api_response(payload, status=status)


def _parse_json() -> Tuple[Optional[dict], Optional[Response]]:
    if not request.data:
        return None, api_error("Request body is required", status=400)
    if not request.is_json:
        return None, api_error("Content-Type must be application/json", status=415, code="unsupported_media_type")
    data = request.get_json(silent=True)
    if data is None:
        return None, api_error("Invalid JSON", status=400)
    return data, None


def _validate_expense_input(data: dict, *, partial: bool) -> Tuple[Optional[dict], Optional[Response]]:
    """Validate expense input: expense_date, amount, category_name, vendor_name, payment_method_name."""
    allowed_keys = {"expense_date", "amount", "category_name", "vendor_name", "payment_method_name", "description", "qty", "unit_price"}
    unknown = [k for k in data.keys() if k not in allowed_keys]
    if unknown:
        return None, api_error("Unknown fields", status=400, details={"unknown": unknown})

    out: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    # expense_date
    if (not partial) or ("expense_date" in data):
        date_val = data.get("expense_date")
        if not date_val:
            errors["expense_date"] = "expense_date is required (YYYY-MM-DD)"
        else:
            try:
                dt.datetime.strptime(str(date_val), "%Y-%m-%d")
                out["expense_date"] = str(date_val)
            except ValueError:
                errors["expense_date"] = "expense_date must be YYYY-MM-DD format"

    # amount
    if (not partial) or ("amount" in data):
        amount = data.get("amount")
        try:
            amount_val = float(amount)
            if amount_val < 0:
                errors["amount"] = "amount must be >= 0"
            else:
                out["amount"] = amount_val
        except (TypeError, ValueError):
            errors["amount"] = "amount is required and must be a number"

    # category_name
    if (not partial) or ("category_name" in data):
        cat = data.get("category_name")
        if not isinstance(cat, str) or not cat.strip():
            errors["category_name"] = "category_name is required and must be a non-empty string"
        elif len(cat.strip()) > 50:
            errors["category_name"] = "category_name must be <= 50 characters"
        else:
            out["category_name"] = cat.strip()

    # vendor_name
    if (not partial) or ("vendor_name" in data):
        vendor = data.get("vendor_name")
        if not isinstance(vendor, str) or not vendor.strip():
            errors["vendor_name"] = "vendor_name is required and must be a non-empty string"
        elif len(vendor.strip()) > 80:
            errors["vendor_name"] = "vendor_name must be <= 80 characters"
        else:
            out["vendor_name"] = vendor.strip()

    # payment_method_name
    if (not partial) or ("payment_method_name" in data):
        payment = data.get("payment_method_name")
        if not isinstance(payment, str) or not payment.strip():
            errors["payment_method_name"] = "payment_method_name is required and must be a non-empty string"
        elif len(payment.strip()) > 30:
            errors["payment_method_name"] = "payment_method_name must be <= 30 characters"
        else:
            out["payment_method_name"] = payment.strip()

    # Optional: description
    if "description" in data:
        desc = data.get("description")
        if desc is None:
            out["description"] = None
        elif not isinstance(desc, str):
            errors["description"] = "description must be a string"
        elif len(desc) > 255:
            errors["description"] = "description must be <= 255 characters"
        else:
            out["description"] = desc

    # Optional: qty
    if "qty" in data:
        qty_val = data.get("qty")
        if qty_val is None:
            out["qty"] = None
        else:
            try:
                q = int(qty_val)
                if q < 0:
                    errors["qty"] = "qty must be >= 0"
                else:
                    out["qty"] = q
            except (TypeError, ValueError):
                errors["qty"] = "qty must be an integer"

    # Optional: unit_price
    if "unit_price" in data:
        up_val = data.get("unit_price")
        if up_val is None:
            out["unit_price"] = None
        else:
            try:
                up = float(up_val)
                if up < 0:
                    errors["unit_price"] = "unit_price must be >= 0"
                else:
                    out["unit_price"] = up
            except (TypeError, ValueError):
                errors["unit_price"] = "unit_price must be a number"

    if errors:
        return None, api_error("Validation failed", status=400, code="validation_error", details=errors)
    
    if not out and partial:
        return None, api_error("At least one field must be provided", status=400, code="validation_error")

    return out, None


def _create_token(app: Flask, *, username: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=app.config["JWT_EXP_SECONDS"])).timestamp()),
    }
    return jwt.encode(payload, app.config["JWT_SECRET"], algorithm=app.config["JWT_ALGORITHM"])


def require_jwt(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return api_error("Missing Bearer token", status=401, code="unauthorized")
        
        token = auth.removeprefix("Bearer ").strip()
        if not token:
            return api_error("Missing Bearer token", status=401, code="unauthorized")

        try:
            jwt.decode(
                token,
                current_app().config["JWT_SECRET"],
                algorithms=[current_app().config["JWT_ALGORITHM"]],
            )
        except jwt.ExpiredSignatureError:
            return api_error("Token expired", status=401, code="token_expired")
        except jwt.InvalidTokenError:
            return api_error("Invalid token", status=401, code="invalid_token")
            
        return fn(*args, **kwargs)
    return wrapper


def current_app() -> Flask:
    from flask import current_app as flask_current_app
    return flask_current_app


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, dt.date):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.json = CustomJSONProvider(app)
    app.config.from_object(config_object)

    if not app.config.get("MYSQL_DB"):
        pass
    
    mysql.init_app(app)

    @app.get("/health")
    def health():
        return api_response({"status": "ok"})

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.post("/auth/login")
    def login():
        data, err = _parse_json()
        if err:
            return err
        
        username = data.get("username")
        password = data.get("password")

        if username != app.config["ADMIN_USERNAME"] or password != app.config["ADMIN_PASSWORD"]:
            return api_error("Invalid credentials", status=401, code="unauthorized")
        
        token = _create_token(app, username=username)
        return api_response({"access_token": token, "token_type": "Bearer"}, status=200)

    def _db_cursor():
        if not app.config.get("MYSQL_DB"):
            raise RuntimeError("MYSQL_DB is not configured. Set MYSQL_DB (and MYSQL_HOST/USER/PASSWORD).")
        return mysql.connection.cursor()

    # === EXPENSE CRUD ENDPOINTS ===
    @app.get("/api/expenses")
    @require_jwt
    def list_expenses():
        try:
            cur = _db_cursor()
            cur.execute("SELECT * FROM expenses_denorm ORDER BY expense_id")
            rows = cur.fetchall()
            return api_response({"data": rows, "count": len(rows)})
        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    @app.get("/api/expenses/<int:expense_id>")
    @require_jwt
    def get_expense(expense_id: int):
        try:
            cur = _db_cursor()
            cur.execute("SELECT * FROM expenses_denorm WHERE expense_id=%s", (expense_id,))
            row = cur.fetchone()
            if not row:
                return api_error("Expense not found", status=404, code="not_found")
            return api_response({"data": row})
        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    @app.post("/api/expenses")
    @require_jwt
    def create_expense():
        data, err = _parse_json()
        if err:
            return err
        
        payload, verr = _validate_expense_input(data, partial=False)
        if verr:
            return verr

        try:
            cur = _db_cursor()
            
            # Resolve dimension keys
            cur.execute(
                "SELECT category_id FROM expense_categories WHERE category_name=%s",
                (payload["category_name"],),
            )
            cat_row = cur.fetchone()
            if not cat_row:
                return api_error("Category not found", status=400, code="not_found", details={"category_name": payload["category_name"]})
            cat_id = cat_row["category_id"]

            cur.execute(
                "SELECT vendor_id FROM vendors WHERE vendor_name=%s",
                (payload["vendor_name"],),
            )
            vendor_row = cur.fetchone()
            if not vendor_row:
                return api_error("Vendor not found", status=400, code="not_found", details={"vendor_name": payload["vendor_name"]})
            vendor_id = vendor_row["vendor_id"]

            cur.execute(
                "SELECT payment_method_id FROM payment_methods WHERE method_name=%s",
                (payload["payment_method_name"],),
            )
            payment_row = cur.fetchone()
            if not payment_row:
                return api_error(
                    "Payment method not found",
                    status=400,
                    code="not_found",
                    details={"payment_method_name": payload["payment_method_name"]},
                )
            pm_id = payment_row["payment_method_id"]

            # Insert expense
            cur.execute(
                """
                INSERT INTO expenses_fact
                (expense_date, amount, category_id, vendor_id, payment_method_id, description, qty, unit_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload["expense_date"],
                    payload["amount"],
                    cat_id,
                    vendor_id,
                    pm_id,
                    payload.get("description"),
                    payload.get("qty"),
                    payload.get("unit_price"),
                ),
            )
            mysql.connection.commit()

            # Get next expense_id
            new_id = cur.lastrowid

            headers = {"Location": f"/api/expenses/{new_id}"}
            return api_response({"data": {"expense_id": new_id, **payload}}, status=201, headers=headers)

        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    @app.put("/api/expenses/<int:expense_id>")
    @require_jwt
    def update_expense(expense_id: int):
        data, err = _parse_json()
        if err:
            return err
        
        payload, verr = _validate_expense_input(data, partial=True)
        if verr:
            return verr

        try:
            cur = _db_cursor()
            cur.execute("SELECT expense_id FROM expenses_fact WHERE expense_id=%s", (expense_id,))
            if not cur.fetchone():
                return api_error("Expense not found", status=404, code="not_found")

            # Resolve dimension IDs if provided
            updates = {}
            if "expense_date" in payload:
                updates["expense_date"] = payload["expense_date"]
            if "amount" in payload:
                updates["amount"] = payload["amount"]
            if "description" in payload:
                updates["description"] = payload["description"]
            if "qty" in payload:
                updates["qty"] = payload["qty"]
            if "unit_price" in payload:
                updates["unit_price"] = payload["unit_price"]

            if "category_name" in payload:
                cur.execute(
                    "SELECT category_id FROM expense_categories WHERE category_name=%s",
                    (payload["category_name"],),
                )
                cat_row = cur.fetchone()
                if not cat_row:
                    return api_error("Category not found", status=400, code="not_found")
                updates["category_id"] = cat_row["category_id"]

            if "vendor_name" in payload:
                cur.execute(
                    "SELECT vendor_id FROM vendors WHERE vendor_name=%s",
                    (payload["vendor_name"],),
                )
                vendor_row = cur.fetchone()
                if not vendor_row:
                    return api_error("Vendor not found", status=400, code="not_found")
                updates["vendor_id"] = vendor_row["vendor_id"]

            if "payment_method_name" in payload:
                cur.execute(
                    "SELECT payment_method_id FROM payment_methods WHERE method_name=%s",
                    (payload["payment_method_name"],),
                )
                payment_row = cur.fetchone()
                if not payment_row:
                    return api_error("Payment method not found", status=400, code="not_found")
                updates["payment_method_id"] = payment_row["payment_method_id"]

            # Build UPDATE statement
            set_parts = [f"{k}=%s" for k in updates.keys()]
            params = list(updates.values()) + [expense_id]
            
            cur.execute(f"UPDATE expenses_fact SET {', '.join(set_parts)} WHERE expense_id=%s", tuple(params))
            mysql.connection.commit()

            cur.execute("SELECT * FROM expenses_denorm WHERE expense_id=%s", (expense_id,))
            row = cur.fetchone()
            return api_response({"data": row})

        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    @app.delete("/api/expenses/<int:expense_id>")
    @require_jwt
    def delete_expense(expense_id: int):
        try:
            cur = _db_cursor()
            cur.execute("DELETE FROM expenses_fact WHERE expense_id=%s", (expense_id,))
            mysql.connection.commit()
            
            if cur.rowcount == 0:
                return api_error("Expense not found", status=404, code="not_found")
            
            return api_response(status=204)
        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    # === SEARCH ENDPOINT ===
    @app.get("/api/expenses/search")
    @require_jwt
    def search_expenses():
        q = (request.args.get("q") or "").strip()
        category = (request.args.get("category") or "").strip()
        vendor = (request.args.get("vendor") or "").strip()
        payment_method = (request.args.get("payment_method") or "").strip()
        min_amount = request.args.get("min_amount")
        max_amount = request.args.get("max_amount")
        start_date = (request.args.get("start_date") or "").strip()
        end_date = (request.args.get("end_date") or "").strip()

        where = []
        params: list[Any] = []

        if q:
            where.append("(description LIKE %s OR vendor_name LIKE %s OR category_name LIKE %s)")
            like = f"%{q}%"
            params.extend([like, like, like])
        
        if category:
            where.append("category_name LIKE %s")
            params.append(f"%{category}%")
        
        if vendor:
            where.append("vendor_name LIKE %s")
            params.append(f"%{vendor}%")
        
        if payment_method:
            where.append("payment_method_name LIKE %s")
            params.append(f"%{payment_method}%")
        
        if min_amount is not None:
            try:
                minp = float(min_amount)
                where.append("amount >= %s")
                params.append(minp)
            except ValueError:
                return api_error("min_amount must be a number", status=400, code="validation_error")

        if max_amount is not None:
            try:
                maxp = float(max_amount)
                where.append("amount <= %s")
                params.append(maxp)
            except ValueError:
                return api_error("max_amount must be a number", status=400, code="validation_error")

        if start_date:
            try:
                dt.datetime.strptime(start_date, "%Y-%m-%d")
                where.append("expense_date >= %s")
                params.append(start_date)
            except ValueError:
                return api_error("start_date must be YYYY-MM-DD", status=400, code="validation_error")

        if end_date:
            try:
                dt.datetime.strptime(end_date, "%Y-%m-%d")
                where.append("expense_date <= %s")
                params.append(end_date)
            except ValueError:
                return api_error("end_date must be YYYY-MM-DD", status=400, code="validation_error")

        if not where:
            return api_error(
                "At least one search parameter is required",
                status=400,
                code="validation_error",
            )

        sql = "SELECT * FROM expenses_denorm"
        sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY expense_id"

        try:
            cur = _db_cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return api_response({"data": rows, "count": len(rows)})
        except Exception as ex:  # noqa: BLE001
            return api_error("Database error", status=500, code="db_error", details=str(ex))

    # === ERROR HANDLERS ===
    @app.errorhandler(404)
    def not_found(_):
        return api_error("Not found", status=404, code="not_found")

    @app.errorhandler(405)
    def method_not_allowed(_):
        return api_error("Method not allowed", status=405, code="method_not_allowed")

    @app.errorhandler(500)
    def internal_error(_):
        return api_error("Internal server error", status=500, code="internal_error")

    @app.route("/api/run-tests", methods=["POST"])
    @require_jwt
    def run_tests():
        """Run the automated test suite and return the results."""
        # Create a stream to capture the output
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        
        # Discover and run tests
        loader = unittest.TestLoader()
        start_dir = 'endpoint_tests'
        suite = loader.discover(start_dir, pattern='*_test.py')
        
        result = runner.run(suite)
        
        output = stream.getvalue()
        
        return api_response({
            "wasSuccessful": result.wasSuccessful(),
            "testsRun": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "output": output
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
