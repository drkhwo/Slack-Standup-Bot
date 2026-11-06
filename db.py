"""Postgres client exposing the slice of the supabase-py query API the bot uses.

Supports table(name).select(cols) / insert(row) / update(values) / upsert(row)
followed by .eq(column, value) filters and .execute(), which returns an object
with .data (a list of dict rows). Each execute() opens its own connection: the
bot runs a handful of queries a day, so pooling is not worth the extra state.
"""
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


class _Query:
    def __init__(self, conninfo, table):
        self._conninfo = conninfo
        self._table = sql.Identifier(table)
        self._op = None
        self._columns = None
        self._values = None
        self._conflict = None
        self._filters = []

    def select(self, columns="*"):
        self._op, self._columns = "select", columns
        return self

    def insert(self, values):
        self._op, self._values = "insert", values
        return self

    def update(self, values):
        self._op, self._values = "update", values
        return self

    def upsert(self, values, on_conflict="key"):
        self._op, self._values, self._conflict = "upsert", values, on_conflict
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def _where(self):
        if not self._filters:
            return sql.SQL(""), []
        clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(
            sql.SQL("{} = %s").format(sql.Identifier(column)) for column, _ in self._filters
        )
        return clause, [value for _, value in self._filters]

    def _build(self):
        where, where_params = self._where()
        if self._op == "select":
            if self._columns == "*":
                columns = sql.SQL("*")
            else:
                columns = sql.SQL(", ").join(sql.Identifier(c.strip()) for c in self._columns.split(","))
            return sql.SQL("SELECT {} FROM {}").format(columns, self._table) + where, where_params

        names = list(self._values)
        params = [self._values[name] for name in names]
        if self._op == "update":
            assignments = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(n)) for n in names)
            query = sql.SQL("UPDATE {} SET {}").format(self._table, assignments) + where
            return query + sql.SQL(" RETURNING *"), params + where_params

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            self._table,
            sql.SQL(", ").join(sql.Identifier(n) for n in names),
            sql.SQL(", ").join(sql.Placeholder() for _ in names),
        )
        if self._op == "upsert":
            updates = [n for n in names if n != self._conflict]
            query += sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
                sql.Identifier(self._conflict),
                sql.SQL(", ").join(sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(n)) for n in updates),
            )
        return query + sql.SQL(" RETURNING *"), params

    def execute(self):
        query, params = self._build()
        with psycopg.connect(self._conninfo, autocommit=True, row_factory=dict_row) as conn:
            rows = conn.execute(query, params).fetchall()
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, conninfo):
        self._conninfo = conninfo

    def table(self, name):
        return _Query(self._conninfo, name)


def create_client(conninfo):
    return Client(conninfo)
