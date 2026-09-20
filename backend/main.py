from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
from sqlalchemy import inspect, text
from backend.database import init_db, engine, SessionLocal, get_db
from backend.config import settings
from backend.models.school import School
from backend.models.user import User, UserRole
from backend.utils.password import hash_password
from datetime import datetime

from backend.routes import auth, students, attendance, grades, fees, dashboard, reports, announcements, schools, staff
from backend.routes.filters import router as filters_router
from backend.routes.settings import router as settings_router
from backend.routes.superadmin import router as superadmin_router
from backend.routes.ai import router as ai_router
from backend.routes.uploads import router as uploads_router
from backend.routes.test_records import router as test_records_router
from backend.routes.teacher import router as teacher_router
from backend.routes.backup import router as backup_router
from backend.routes.parent import router as parent_router

# ✅ ERROR MONITORING (Sentry) — initialized before the app is created so it
# captures everything, including startup failures. Fully optional: without
# SENTRY_DSN set, this block is a no-op and the app behaves exactly as before.
if settings.SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            # Only error events — no performance tracing, keeps free-tier
            # quota for what matters (errors) and adds no request overhead.
            traces_sample_rate=0.0,
            # Don't attach request bodies/local variables — school data
            # (student names, fees) must not end up in a third-party tool.
            send_default_pii=False,
        )
        print(f"✅ Sentry error monitoring enabled ({settings.SENTRY_ENVIRONMENT})")
    except Exception as _sentry_err:  # monitoring must never break the app
        print(f"⚠️ Sentry init failed (continuing without it): {_sentry_err}")

# ✅ NON-DESTRUCTIVE AUTO-MIGRATION
# Base.metadata.create_all() only creates NEW tables — it never adds new
# columns to a table that already exists in school.db. So when a model gains
# a field (e.g. Staff.role), existing databases break with
# "table X has no column named Y" until the column is added manually.
# This helper adds any missing columns WITHOUT touching existing rows/data.
#
# IMPORTANT (cold-start latency): this runs on EVERY serverless cold start,
# and each DB round-trip costs real time against a free-tier Supabase
# Postgres instance. Checking columns ONE AT A TIME (7 separate
# inspector.get_columns() calls) was adding up to 7 extra round-trips before
# any request could be served — batched here to ONE get_columns() call per
# TABLE (4 calls total) instead of per COLUMN, since several columns landed
# on the same table (schools, staff, users).
def _ensure_columns(inspector, existing_tables: set[str], table_name: str, columns: dict[str, str]):
    if table_name not in existing_tables:
        return  # table doesn't exist yet — create_all() will create it fully
    try:
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        missing = {name: ddl for name, ddl in columns.items() if name not in existing_columns}
        if not missing:
            return
        with engine.connect() as conn:
            for column_name, column_ddl in missing.items():
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_ddl}"))
                print(f"✅ Migrated: added missing column '{column_name}' to '{table_name}'")
            conn.commit()
    except Exception as e:
        print(f"⚠️ Migration check failed for table '{table_name}': {e}")

app = FastAPI(
    title="School Management System",
    description="Professional School Management Solution"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://127.0.0.1:5501",
        "http://127.0.0.1:8080",
        "http://localhost:5500",
        "http://localhost:5501",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Baseline hardening headers — cheap, safe, and standard practice.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(traceback.format_exc())
        # This middleware swallows the exception (returns a JSON 500 instead
        # of re-raising), so Sentry's automatic integration never sees it —
        # capture it explicitly here.
        if settings.SENTRY_DSN:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
                # CRITICAL on Vercel: the function freezes as soon as the
                # response is returned, so Sentry's background sender never
                # runs. flush() blocks (max 3s) until the event is actually
                # delivered — without this, no error ever reaches Sentry.
                sentry_sdk.flush(timeout=3)
            except Exception:
                pass  # monitoring must never break the response
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
        )
        # ✅ FIX: error_handling_middleware runs OUTSIDE CORSMiddleware, so its
        # responses were missing CORS headers — browsers then reported a
        # confusing "blocked by CORS policy" instead of the real 500 error.
        # Manually echo the CORS headers here so the real error reaches the frontend.
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

# ✅ AUTO DATABASE INITIALIZATION ON STARTUP
@app.on_event("startup")
async def startup():
    try:
        print("\n" + "="*60)
        print("🚀 INITIALIZING DATABASE...")
        print("="*60)

        # Heal any existing database that was created before these columns existed.
        # One inspector + one get_table_names() call, reused across all tables.
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        _ensure_columns(inspector, existing_tables, "schools", {
            "city": "city VARCHAR(50)",
            "is_active": "is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "parent_portal_enabled": "parent_portal_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "parent_show_attendance": "parent_show_attendance BOOLEAN NOT NULL DEFAULT TRUE",
            "parent_show_grades": "parent_show_grades BOOLEAN NOT NULL DEFAULT TRUE",
            "parent_show_fees": "parent_show_fees BOOLEAN NOT NULL DEFAULT TRUE",
            "parent_show_documents": "parent_show_documents BOOLEAN NOT NULL DEFAULT FALSE",
            "parent_allow_messages": "parent_allow_messages BOOLEAN NOT NULL DEFAULT TRUE",
            "payment_info": "payment_info TEXT",
            "background_image_url": "background_image_url VARCHAR(500)",
            "background_image_enabled": "background_image_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "background_overlay": "background_overlay INTEGER NOT NULL DEFAULT 82",
        })
        _ensure_columns(inspector, existing_tables, "staff", {
            "role": "role VARCHAR(20) NOT NULL DEFAULT 'teacher'",
            "user_id": "user_id INTEGER",
        })
        _ensure_columns(inspector, existing_tables, "students", {
            "photo_url": "photo_url VARCHAR(500)",
            "parent_email": "parent_email VARCHAR(150)",
            "parent_user_id": "parent_user_id INTEGER",
        })
        _ensure_columns(inspector, existing_tables, "users", {
            "failed_login_attempts": "failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "locked_until": "locked_until TIMESTAMP",
        })
        _ensure_columns(inspector, existing_tables, "attendance", {
            "marked_by_user_id": "marked_by_user_id INTEGER",
        })

        # ⚠️ SECURITY: these two secrets, if left at their placeholder default,
        # let anyone forge admin tokens or access the super-admin panel for
        # EVERY school on this deployment. Loud warning instead of silently
        # continuing — fix by setting real random values in Vercel's env vars.
        if settings.JWT_SECRET == "replace_with_a_strong_random_secret":
            print("🚨🚨🚨 SECURITY WARNING: JWT_SECRET is still the default placeholder! "
                  "Anyone can forge login tokens. Set a real random JWT_SECRET immediately.")
        if not settings.SUPER_ADMIN_SECRET:
            print("⚠️  SUPER_ADMIN_SECRET is not set — the super-admin panel route is unreachable "
                  "(fails closed), which is safe, but set it if you actually use that panel.")

        # Initialize all tables
        init_db()
        print("✅ Database tables created/verified")
        
        # Demo account is only created in DEBUG mode (local development).
        # In production (DEBUG=False, the default), this is skipped entirely —
        # a publicly-known login (admin@school.com / admin123) has no place
        # on a server hosting real schools' data, especially since this
        # source code is on a public GitHub repo.
        if settings.DEBUG:
            db = SessionLocal()
            try:
                existing_school = db.query(School).filter(School.name == "Demo School").first()
                existing_user = db.query(User).filter(User.email == "admin@school.com").first()

                if existing_school and existing_user:
                    print("✅ Demo data already exists")
                    print(f"   School: {existing_school.name}")
                    print(f"   Admin: {existing_user.email}")
                else:
                    print("\n📝 Creating Demo Data...")

                    # Create demo school
                    school = School(
                        name="Demo School",
                        email="admin@school.com",
                        phone="03001234567",
                        city="Lahore",
                        address="Demo Address",
                        password_hash=hash_password("admin123"),
                    )
                    db.add(school)
                    db.commit()
                    db.refresh(school)
                    print(f"✅ School created: {school.name} (ID: {school.id})")

                    # Create demo admin user
                    admin_user = User(
                        school_id=school.id,
                        username="admin",
                        email="admin@school.com",
                        password_hash=hash_password("admin123"),
                        full_name="Admin User",
                        role=UserRole.admin,
                        is_active=True,
                    )
                    db.add(admin_user)
                    db.commit()
                    db.refresh(admin_user)
                    print(f"✅ Admin user created: {admin_user.email}")

                print("\n" + "="*60)
                print("✅ DATABASE INITIALIZATION COMPLETE!")
                print("="*60)
                print("\n📌 DEMO CREDENTIALS (DEBUG mode only):")
                print("   Email: admin@school.com")
                print("   Password: admin123")
                print("\n" + "="*60 + "\n")

            except Exception as e:
                print(f"❌ Error creating demo data: {e}")
                db.rollback()
            finally:
                db.close()
        else:
            print("✅ Database initialization complete (production mode — demo account skipped)")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print(traceback.format_exc())

print("🔄 Loading routes...")
app.include_router(auth.router, tags=["auth"])
print("✅ Auth routes loaded")
app.include_router(schools.router, tags=["schools"])
print("✅ Schools routes loaded")
app.include_router(students.router, tags=["students"])
print("✅ Students routes loaded")
app.include_router(attendance.router, tags=["attendance"])
print("✅ Attendance routes loaded")
app.include_router(grades.router, tags=["grades"])
print("✅ Grades routes loaded")
app.include_router(fees.router, tags=["fees"])
print("✅ Fees routes loaded")
app.include_router(dashboard.router, tags=["dashboard"])
print("✅ Dashboard routes loaded")
app.include_router(reports.router, tags=["reports"])
print("✅ Reports routes loaded")
app.include_router(announcements.router, tags=["announcements"])
print("✅ Announcements routes loaded")
app.include_router(staff.router, tags=["staff"])
print("✅ Staff routes loaded")
app.include_router(filters_router, tags=["filters"])
print("✅ Filters routes loaded")
app.include_router(settings_router, tags=["settings"])
print("✅ Settings routes loaded")
app.include_router(superadmin_router, tags=["superadmin"])
print("✅ Super admin routes loaded")
app.include_router(ai_router, tags=["ai"])
print("✅ AI routes loaded")
app.include_router(uploads_router, tags=["student-documents"])
print("✅ Student document upload routes loaded")
app.include_router(test_records_router, tags=["test-records"])
print("✅ Test record routes loaded")
app.include_router(teacher_router, tags=["teacher-portal"])
print("✅ Teacher portal routes loaded")
app.include_router(backup_router, tags=["backup"])
print("✅ Backup routes loaded")
app.include_router(parent_router, tags=["parent-portal"])
print("✅ Parent portal routes loaded")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Server is running",
        "cors": "enabled"
    }

@app.get("/keep-alive")
async def keep_alive(db: Session = Depends(get_db)):
    """
    Touches the database with a trivial query. Exists purely so an external
    uptime pinger (e.g. UptimeRobot, free) can hit this every few days and
    keep a free-tier Supabase project from auto-pausing due to inactivity.
    /health above does NOT query the database, so it wouldn't count as
    activity from Supabase's perspective — this endpoint specifically does.
    """
    db.execute(text("SELECT 1"))
    return {"status": "alive"}

@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"message": "OK"}

# ==================== SERVE FRONTEND (same origin as API) ====================
# Mounted LAST and at "/" so it never shadows the API routes registered above —
# FastAPI matches routes in registration order, and this is a catch-all fallback.
# Serving frontend + API from one origin means the browser's window.location.origin
# always equals the API base, so no hardcoded URLs and no CORS issues in production.
import os
from fastapi.staticfiles import StaticFiles

_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
    print(f"✅ Frontend mounted from {_frontend_dir}")
else:
    print(f"⚠️  Frontend directory not found at {_frontend_dir} — API-only mode")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)