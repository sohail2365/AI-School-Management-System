"""
One-time migration: add `background_overlay` column to schools table.
Run: python -m backend.scripts.add_overlay_column
"""
from sqlalchemy import text
from backend.database import engine


def run():
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE schools ADD COLUMN background_overlay INTEGER NOT NULL DEFAULT 82"
            ))
            conn.commit()
            print("[OK] Column `background_overlay` added to `schools` table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column" in err or "already exists" in err:
                print("[SKIP] Column `background_overlay` already exists.")
            else:
                print(f"[ERROR] Migration failed: {e}")
                raise


if __name__ == "__main__":
    run()