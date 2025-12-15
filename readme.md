# CS-ELECTIVE-FINAL-PROJECT-ERL

CRUD REST API Final Project (CSE1) using Flask + MySQL.

## Features
- CRUD REST API for a Cost Tracker (`expenses`)
- Normalized Star Schema Database (Fact: `expenses_fact`, Dimensions: `expense_categories`, `vendors`, `payment_methods`)
- Input validation + error handling with appropriate HTTP status codes
- Output format option via `?format=json` (default) or `?format=xml`
- Search endpoint with multiple criteria (category, vendor, date range, amount range)
- JWT authentication (Bearer token)
- Test suite covering CRUD + auth + formatting

## Requirements
- Python 3.10+
- MySQL Server running locally (or reachable over network)

## Setup
1) Create and activate a virtual environment.

2) Install dependencies:
`pip install -r requirements.txt`

3) Configure environment variables (PowerShell examples):
`$env:MYSQL_HOST="localhost"`

`$env:MYSQL_USER="root"`

`$env:MYSQL_PASSWORD="your_password"`

`$env:MYSQL_DB="your_database"`

Optional:
`$env:MYSQL_PORT="3306"`

JWT settings (recommended to change):
`$env:JWT_SECRET="a-strong-secret"`

Admin login used for `/auth/login`:
`$env:ADMIN_USERNAME="admin"`

`$env:ADMIN_PASSWORD="admin"`

## Database schema + seed data
This project uses a normalized schema for tracking expenses.
Main view: `expenses_denorm` (joins fact table with dimensions).

To create the tables (if missing) and seed at least 20 records:
`python -m endpoint_tests.data_create`

## Run the API
`python app.py`

Server starts on `http://localhost:5000`.

## Authentication (JWT)
1) Login:

`POST /auth/login`

Body:
`{"username":"admin","password":"admin"}`

2) Use the returned token in requests:

Header:
`Authorization: Bearer <token>`

## API Endpoints
All `/api/*` endpoints require JWT.

- `GET /health`
- `POST /auth/login`

### Expenses
- `GET /api/expenses`
- `GET /api/expenses/<id>`
- `POST /api/expenses`
- `PUT /api/expenses/<id>`
- `DELETE /api/expenses/<id>`

Example create:
`POST /api/expenses`

Body:
```json
{
  "expense_date": "2025-12-25",
  "amount": 500.00,
  "category_name": "Food",
  "vendor_name": "Jollibee",
  "payment_method_name": "Cash",
  "description": "Christmas dinner",
  "qty": 4,
  "unit_price": 125.00
}
```

### Search
- `GET /api/expenses/search?category=Food`

Supported parameters: `category`, `vendor`, `min_amount`, `max_amount`, `start_date`, `end_date`.

## Output format (XML/JSON)
Add the URI parameter `format`:
- JSON: `?format=json` (default)
- XML: `?format=xml`

Example:
`GET /api/expenses?format=xml`

## Run tests
Tests require the same MySQL environment variables to be set.

`python -m unittest endpoint_tests.api_test`
