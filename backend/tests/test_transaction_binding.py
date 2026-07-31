"""Statements inside a transaction must be inside that transaction.

pg_client.transaction() yields a dedicated connection, but most callers wrote
`async with pg_client.transaction(...)` without binding it and then used
pg_client.execute(). Those calls acquired a different pooled connection, so they
ran outside the transaction: a compensation change committed to employee_pii
while its comp_history row rolled back, leaving a pay rise with no audit record.

Run directly: python -m tests.test_transaction_binding
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.postgres_client import pg_client  # noqa: E402

TABLE = "tx_binding_check"


async def main() -> int:
    await pg_client.connect()
    await pg_client.execute(f"DROP TABLE IF EXISTS {TABLE}")
    await pg_client.execute(f"CREATE TABLE {TABLE} (id INT PRIMARY KEY)")

    # A write made through the module-level helper, inside a transaction that
    # then fails, must not survive.
    try:
        async with pg_client.transaction("test", "rollback_check"):
            await pg_client.execute(f"INSERT INTO {TABLE} (id) VALUES (1)")
            raise RuntimeError("forced failure after the write")
    except RuntimeError:
        pass

    row = await pg_client.fetchrow(f"SELECT COUNT(*) AS n FROM {TABLE}")
    survived = int(row["n"])
    assert survived == 0, (
        f"{survived} row(s) survived a rolled-back transaction: the write ran on a "
        "different connection and committed on its own")

    # And a transaction that succeeds must still commit.
    async with pg_client.transaction("test", "commit_check"):
        await pg_client.execute(f"INSERT INTO {TABLE} (id) VALUES (2)")

    row = await pg_client.fetchrow(f"SELECT COUNT(*) AS n FROM {TABLE}")
    assert int(row["n"]) == 1, "a committed transaction did not persist its write"

    # Reads inside a transaction must see that transaction's own uncommitted work.
    async with pg_client.transaction("test", "read_own_writes"):
        await pg_client.execute(f"INSERT INTO {TABLE} (id) VALUES (3)")
        row = await pg_client.fetchrow(f"SELECT COUNT(*) AS n FROM {TABLE}")
        assert int(row["n"]) == 2, "a read inside the transaction could not see its own write"

    await pg_client.execute(f"DROP TABLE {TABLE}")
    await pg_client.close()
    print("PASS  writes through pg_client honour the surrounding transaction")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
