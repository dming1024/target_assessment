#!/usr/bin/env python3
"""
Incremental updater for the offline SQLite database.

Updates individual tables in target_assessment.db without requiring
a full rebuild. Backs up the existing database before making changes.

Usage:
    # Update specific tables
    python3.8 data/update_offline_db.py --table genes
    python3.8 data/update_offline_db.py --table depmap_crispr
    python3.8 data/update_offline_db.py --table tcga           # Both TCGA tables
    python3.8 data/update_offline_db.py --table opentargets
    python3.8 data/update_offline_db.py --table chembl

    # Dry-run (check without modifying)
    python3.8 data/update_offline_db.py --table depmap_crispr --dry-run

    # Full rebuild with backup
    python3.8 data/update_offline_db.py --full

    # Full rebuild without confirmation
    python3.8 data/update_offline_db.py --full --yes

Supported tables:
    genes           NCBI gene info (symbols, Ensembl IDs, aliases)
    depmap_crispr   DepMap CRISPR dependency scores
    tcga            Both TCGA expression and mutation tables
    tcga_expression TCGA expression data only
    tcga_mutation   TCGA mutation data only
    opentargets     Open Targets target-disease associations
    chembl          ChEMBL drug counts by target
"""

import argparse
import logging
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PROCESSED_DIR, OFFLINE_DB

# Reuse import functions from build_offline_db
from data.build_offline_db import (
    import_genes,
    import_depmap,
    import_tcga_expression,
    import_tcga_mutation,
    import_opentargets,
    import_chembl,
    SCHEMA,
    INDEXES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("update_offline_db")

# ── Backup & validation ───────────────────────────────────────────────────

def backup_database(db_path: Path) -> Path:
    """Create a timestamped backup of the database. Returns backup path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"target_assessment_backup_{timestamp}.db"
    logger.info(f"Backing up database → {backup_path}")
    shutil.copy2(db_path, backup_path)
    backup_size = backup_path.stat().st_size / 1024 / 1024
    logger.info(f"  backup size: {backup_size:.0f} MB")
    return backup_path


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists in the database."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        [table],
    ).fetchone()
    return row is not None


def get_table_count(conn: sqlite3.Connection, table: str) -> int:
    """Get the row count of a table (0 if table doesn't exist)."""
    if not table_exists(conn, table):
        return 0
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def validate_updated_table(conn: sqlite3.Connection, table: str, min_rows: int = 1) -> bool:
    """Validate that a table exists and has at least min_rows rows."""
    if not table_exists(conn, table):
        logger.error(f"  ✗ Table '{table}' does not exist after import")
        return False
    count = get_table_count(conn, table)
    if count < min_rows:
        logger.error(f"  ✗ Table '{table}' has only {count} rows (expected ≥ {min_rows})")
        return False
    logger.info(f"  ✓ Table '{table}': {count:,} rows")
    return True


def ensure_schema(conn: sqlite3.Connection):
    """Ensure all required tables exist (create if missing)."""
    conn.executescript(SCHEMA)
    conn.commit()


def ensure_indexes(conn: sqlite3.Connection):
    """Create or recreate all indexes."""
    for idx_sql in INDEXES:
        try:
            conn.execute(idx_sql)
        except sqlite3.OperationalError as e:
            logger.warning(f"  Index warning: {e}")
    conn.commit()


# ── Per-table update handlers ─────────────────────────────────────────────

def update_genes(conn: sqlite3.Connection) -> bool:
    """Update the genes table from NCBI gene info."""
    logger.info("=" * 60)
    logger.info("Updating: genes")
    t0 = time.time()

    # Backup old data in case we need to roll back in-memory
    old_count = get_table_count(conn, "genes")
    logger.info(f"  current rows: {old_count:,}")

    # Drop and recreate (import_genes uses INSERT OR REPLACE, so we can keep
    # the table and let it do the work)
    import_genes(conn, PROCESSED_DIR)

    count = get_table_count(conn, "genes")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


def update_depmap(conn: sqlite3.Connection) -> bool:
    """Update the depmap_crispr table from local CSV."""
    logger.info("=" * 60)
    logger.info("Updating: depmap_crispr")
    t0 = time.time()

    old_count = get_table_count(conn, "depmap_crispr")
    logger.info(f"  current rows: {old_count:,}")

    csv_path = PROCESSED_DIR / "depmap_crispr_summary.csv"
    if not csv_path.exists():
        logger.error(f"  ✗ CSV not found: {csv_path}")
        logger.error("  Place the new CSV file at the path above and retry.")
        return False

    import_depmap(conn)

    count = get_table_count(conn, "depmap_crispr")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


def update_tcga_expression(conn: sqlite3.Connection) -> bool:
    """Update the tcga_expression table from local CSV."""
    logger.info("-" * 40)
    logger.info("Updating: tcga_expression")
    t0 = time.time()

    old_count = get_table_count(conn, "tcga_expression")
    logger.info(f"  current rows: {old_count:,}")

    csv_path = PROCESSED_DIR / "tcga_expression_summary.csv"
    if not csv_path.exists():
        logger.error(f"  ✗ CSV not found: {csv_path}")
        logger.error("  Place the new CSV file at the path above and retry.")
        return False

    import_tcga_expression(conn)

    count = get_table_count(conn, "tcga_expression")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


def update_tcga_mutation(conn: sqlite3.Connection) -> bool:
    """Update the tcga_mutation table from local CSV."""
    logger.info("-" * 40)
    logger.info("Updating: tcga_mutation")
    t0 = time.time()

    old_count = get_table_count(conn, "tcga_mutation")
    logger.info(f"  current rows: {old_count:,}")

    csv_path = PROCESSED_DIR / "tcga_mutation_summary.csv"
    if not csv_path.exists():
        logger.error(f"  ✗ CSV not found: {csv_path}")
        logger.error("  Place the new CSV file at the path above and retry.")
        return False

    import_tcga_mutation(conn)

    count = get_table_count(conn, "tcga_mutation")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


def update_tcga(conn: sqlite3.Connection) -> bool:
    """Update both TCGA tables."""
    ok_expr = update_tcga_expression(conn)
    ok_mut = update_tcga_mutation(conn)
    return ok_expr and ok_mut


def update_opentargets(conn: sqlite3.Connection) -> bool:
    """Update the opentargets table (downloads ~500 MB)."""
    logger.info("=" * 60)
    logger.info("Updating: opentargets")
    t0 = time.time()

    old_count = get_table_count(conn, "opentargets")
    logger.info(f"  current rows: {old_count:,}")

    # import_opentargets handles download + import
    try:
        import_opentargets(conn, PROCESSED_DIR)
    except Exception as e:
        logger.error(f"  ✗ Open Targets import failed: {e}")
        return False

    count = get_table_count(conn, "opentargets")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


def update_chembl(conn: sqlite3.Connection) -> bool:
    """Update the chembl_drugs table (downloads ~800 MB if not cached)."""
    logger.info("=" * 60)
    logger.info("Updating: chembl_drugs")
    t0 = time.time()

    old_count = get_table_count(conn, "chembl_drugs")
    logger.info(f"  current rows: {old_count:,}")

    try:
        import_chembl(conn, PROCESSED_DIR)
    except Exception as e:
        logger.error(f"  ✗ ChEMBL import failed: {e}")
        return False

    count = get_table_count(conn, "chembl_drugs")
    logger.info(f"  new rows: {count:,}")
    logger.info(f"  done in {time.time() - t0:.1f}s")
    return count > 0


# ── Main ──────────────────────────────────────────────────────────────────

TABLE_HANDLERS = {
    "genes": update_genes,
    "depmap_crispr": update_depmap,
    "tcga": update_tcga,
    "tcga_expression": update_tcga_expression,
    "tcga_mutation": update_tcga_mutation,
    "opentargets": update_opentargets,
    "chembl": update_chembl,
}


def run_update(table: str, dry_run: bool = False) -> bool:
    """Update a single table in the offline database."""
    db_path = Path(OFFLINE_DB)

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Build it first with: python3.8 data/build_offline_db.py")
        return False

    handler = TABLE_HANDLERS.get(table)
    if handler is None:
        logger.error(f"Unknown table: {table}")
        logger.error(f"Available tables: {', '.join(TABLE_HANDLERS)}")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Would update table: {table}")
        conn = sqlite3.connect(str(db_path))
        old_count = 0
        try:
            # Find the mapping for TCGA tables
            if table == "tcga":
                ec = get_table_count(conn, "tcga_expression")
                mc = get_table_count(conn, "tcga_mutation")
                logger.info(f"  current tcga_expression: {ec:,} rows")
                logger.info(f"  current tcga_mutation:   {mc:,} rows")
            else:
                # Map aliases to actual table names
                table_map = {
                    "depmap_crispr": "depmap_crispr",
                    "opentargets": "opentargets",
                    "chembl": "chembl_drugs",
                    "genes": "genes",
                    "tcga_expression": "tcga_expression",
                    "tcga_mutation": "tcga_mutation",
                }
                actual_table = table_map.get(table, table)
                old_count = get_table_count(conn, actual_table)
                logger.info(f"  current rows: {old_count:,}")
        finally:
            conn.close()
        return True

    # Create backup
    backup_path = backup_database(db_path)

    # Connect and update
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        ensure_schema(conn)
        success = handler(conn)

        if success:
            # Rebuild indexes
            logger.info("Rebuilding indexes...")
            t0 = time.time()
            ensure_indexes(conn)
            logger.info(f"  indexes rebuilt in {time.time() - t0:.1f}s")

            # Validate
            logger.info("Validating updated tables...")
            table_map = {
                "genes": ("genes", 100_000),
                "depmap_crispr": ("depmap_crispr", 1_000),
                "tcga": ("tcga_expression", 1_000),
                "tcga_expression": ("tcga_expression", 1_000),
                "tcga_mutation": ("tcga_mutation", 1_000),
                "opentargets": ("opentargets", 10_000),
                "chembl": ("chembl_drugs", 100),
            }

            if table == "tcga":
                ok1 = validate_updated_table(conn, "tcga_expression", 1_000)
                ok2 = validate_updated_table(conn, "tcga_mutation", 1_000)
                all_ok = ok1 and ok2
            else:
                tbl, min_rows = table_map.get(table, (table, 1))
                all_ok = validate_updated_table(conn, tbl, min_rows)

            if all_ok:
                db_size = db_path.stat().st_size / 1024 / 1024
                logger.info("=" * 60)
                logger.info("Update complete ✓")
                logger.info(f"  database: {db_path} ({db_size:.0f} MB)")
                logger.info(f"  backup:   {backup_path}")
            else:
                logger.error("=" * 60)
                logger.error("Validation failed — rolling back")
                conn.close()
                # Restore from backup
                db_path.unlink()
                shutil.move(str(backup_path), str(db_path))
                logger.info("Database restored from backup.")
                return False
        else:
            logger.error("=" * 60)
            logger.error("Update failed — rolling back")
            conn.close()
            # Restore from backup
            db_path.unlink()
            shutil.move(str(backup_path), str(db_path))
            logger.info("Database restored from backup.")
            return False

    except Exception as e:
        logger.error(f"Update failed with exception: {e}")
        logger.error("Rolling back...")
        try:
            conn.close()
        except Exception:
            pass
        db_path.unlink()
        shutil.move(str(backup_path), str(db_path))
        logger.info("Database restored from backup.")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return True


def run_full_update(dry_run: bool = False, skip_confirm: bool = False):
    """Run a full rebuild of all tables."""
    if dry_run:
        logger.info("[DRY RUN] Would perform full rebuild of all tables")
        db_path = Path(OFFLINE_DB)
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                for table in ["genes", "opentargets", "chembl_drugs",
                              "depmap_crispr", "tcga_expression", "tcga_mutation"]:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    logger.info(f"  {table:25s}: {count:>10,} rows")
            finally:
                conn.close()
        else:
            logger.info("  No existing database found — would build a new one")
        return

    if not skip_confirm:
        print()
        print("This will rebuild ALL tables in the offline database.")
        print("A backup of the current database will be created.")
        print("Approximate download: ~1.5 GB (Open Targets + ChEMBL + NCBI Gene)")
        print("Approximate time: 10–30 minutes")
        print()
        response = input("Proceed? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Cancelled.")
            return

    db_path = Path(OFFLINE_DB)
    backup_path = None
    if db_path.exists():
        backup_path = backup_database(db_path)

    # Run all updates on the existing (or new) connection
    tables = ["genes", "depmap_crispr", "tcga", "opentargets", "chembl"]
    failed = []

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        ensure_schema(conn)

        for table in tables:
            try:
                handler = TABLE_HANDLERS[table]
                ok = handler(conn)
                if not ok:
                    failed.append(table)
                    logger.error(f"  ✗ {table} update returned failure")
            except Exception as e:
                failed.append(table)
                logger.error(f"  ✗ {table} update raised exception: {e}")

        if not failed:
            logger.info("Rebuilding indexes...")
            t0 = time.time()
            ensure_indexes(conn)
            logger.info(f"  indexes rebuilt in {time.time() - t0:.1f}s")

            # Summary
            logger.info("=" * 60)
            logger.info("Full update complete ✓")
            for table in ["genes", "opentargets", "chembl_drugs",
                          "depmap_crispr", "tcga_expression", "tcga_mutation"]:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                logger.info(f"  {table:25s}: {count:>10,} rows")
            db_size = db_path.stat().st_size / 1024 / 1024
            logger.info(f"  database size: {db_size:.0f} MB")
            if backup_path:
                logger.info(f"  backup: {backup_path}")
        else:
            logger.error(f"Failed tables: {', '.join(failed)}")
            logger.error("Rolling back entire update...")
            conn.close()
            if backup_path:
                db_path.unlink()
                shutil.move(str(backup_path), str(db_path))
                logger.info("Database restored from backup.")
    except Exception as e:
        logger.error(f"Full update failed: {e}")
        conn.close()
        if backup_path and db_path.exists():
            db_path.unlink()
        if backup_path:
            shutil.move(str(backup_path), str(db_path))
            logger.info("Database restored from backup.")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Incrementally update the offline SQLite database"
    )
    parser.add_argument(
        "--table", "-t",
        choices=list(TABLE_HANDLERS),
        help="Table to update (omit with --full for all tables)"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Rebuild all tables (full database refresh)"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt (for --full)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be updated without making changes"
    )
    args = parser.parse_args()

    if not args.table and not args.full:
        parser.error("Must specify --table <name> or --full")

    if args.full:
        run_full_update(dry_run=args.dry_run, skip_confirm=args.yes)
    else:
        ok = run_update(args.table, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)
