import re
import sqlite3 as sql
from contextlib import contextmanager
from threading import RLock

from paths import db_path


_identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_db_lock = RLock()
_initialized = False


def _validate_identifier(value):
	if not _identifier.match(value):
		raise ValueError(f"Invalid database identifier: {value}")


def db_init():
	con = sql.connect(db_path, timeout=30)
	con.row_factory = sql.Row
	con.execute("pragma busy_timeout=30000")
	con.execute("pragma foreign_keys=on")
	con.execute("pragma journal_mode=wal")
	con.execute("pragma synchronous=normal")
	return con


@contextmanager
def connection(write=False):
	ensure_database()
	con = db_init()
	try:
		if write:
			with _db_lock:
				yield con
				con.commit()
		else:
			yield con
	except Exception:
		if write:
			con.rollback()
		raise
	finally:
		con.close()


@contextmanager
def _bootstrap_connection():
	con = db_init()
	try:
		with _db_lock:
			yield con
			con.commit()
	except Exception:
		con.rollback()
		raise
	finally:
		con.close()


def is_valid(function):
	def rapper(*args, **kwargs):
		ensure_database()
		return function(*args, **kwargs)
	return rapper


def ensure_database():
	global _initialized
	if _initialized:
		return
	with _db_lock:
		if _initialized:
			return
		prepare_tables()
		_initialized = True


def prepare_tables():
	with _bootstrap_connection() as con:
		favorites_query = """
create table if not exists favorite (
	id integer primary key,
	title text not null,
	display_title text not null,
	url text not null,
	is_live integer not null,
	channel_name text not null,
	channel_url text not null,
	item_type text not null default 'video'
)"""
		con.execute(favorites_query)
		ensure_column("favorite", "item_type", "text not null default 'video'", con)
		con.execute("delete from favorite where id not in (select max(id) from favorite group by url)")
		con.execute("create unique index if not exists idx_favorite_url on favorite(url)")

		continue_query = """
create table if not exists continue (
	id integer primary key,
	url text not null,
	position real not null
)"""
		con.execute(continue_query)
		con.execute("delete from continue where id not in (select max(id) from continue group by url)")
		con.execute("create unique index if not exists idx_continue_url on continue(url)")


def ensure_column(table, column, definition, con=None):
	_validate_identifier(table)
	_validate_identifier(column)
	if con is None:
		with connection(write=True) as con:
			ensure_column(table, column, definition, con)
		return
	columns = [row["name"] for row in con.execute(f"pragma table_info({table})").fetchall()]
	if column not in columns:
		con.execute(f"alter table {table} add column {column} {definition}")


def disconnect():
	# Connections are short-lived and closed after each operation. This function is
	# kept for application shutdown compatibility.
	pass


class Favorite:
	@is_valid
	def add_favorite(self, data):
		query = """
insert into favorite (title, display_title, url, is_live, channel_name, channel_url, item_type)
values (?, ?, ?, ?, ?, ?, ?)
on conflict(url) do update set
	title=excluded.title,
	display_title=excluded.display_title,
	is_live=excluded.is_live,
	channel_name=excluded.channel_name,
	channel_url=excluded.channel_url,
	item_type=excluded.item_type
"""
		with connection(write=True) as con:
			con.execute(query, (
				data["title"],
				data["display_title"],
				data["url"],
				data.get("live", 0),
				data.get("channel_name", ""),
				data.get("channel_url", ""),
				data.get("item_type", "video"),
			))

	@is_valid
	def remove_favorite(self, url):
		with connection(write=True) as con:
			con.execute("delete from favorite where url=?", (url,))

	@is_valid
	def get_all(self):
		query = """
select title, display_title, url, is_live, channel_name, channel_url, item_type
from favorite
order by id
"""
		with connection() as con:
			cursor = con.execute(query).fetchall()
		data = []
		for row in cursor:
			data.append({
				"title": row["title"],
				"display_title": row["display_title"],
				"url": row["url"],
				"live": row["is_live"],
				"channel_name": row["channel_name"],
				"channel_url": row["channel_url"],
				"item_type": row["item_type"] or "video",
			})
		return data

	@is_valid
	def exists(self, url):
		with connection() as con:
			return con.execute("select 1 from favorite where url=? limit 1", (url,)).fetchone() is not None


class Continue:
	@classmethod
	@is_valid
	def new_continue(cls, url, position):
		query = """
insert into continue (url, position)
values (?, ?)
on conflict(url) do update set position=excluded.position
"""
		with connection(write=True) as con:
			con.execute(query, (url, position))

	@classmethod
	@is_valid
	def get_all(cls):
		with connection() as con:
			cursor = con.execute("select url, position from continue").fetchall()
		return {row["url"]: row["position"] for row in cursor}

	@classmethod
	@is_valid
	def update(cls, url, position):
		Continue.new_continue(url, position)

	@classmethod
	@is_valid
	def remove_continue(cls, url):
		with connection(write=True) as con:
			con.execute("delete from continue where url=?", (url,))


ensure_database()
