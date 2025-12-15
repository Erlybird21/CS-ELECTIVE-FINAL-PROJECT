
import os


class Config:
	# Flask
	SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev")

	# MySQL (Flask-MySQLdb expects these names)
	MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
	MYSQL_USER = os.getenv("MYSQL_USER", "root")
	MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root123")
	MYSQL_DB = os.getenv("MYSQL_DB", "cost_tracker")
	MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
	MYSQL_CURSORCLASS = os.getenv("MYSQL_CURSORCLASS", "DictCursor")

	# JWT
	JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
	JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
	JWT_EXP_SECONDS = int(os.getenv("JWT_EXP_SECONDS", "3600"))

	# Simple admin auth for demo/login
	ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
	ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")


class TestConfig(Config):
	TESTING = True

