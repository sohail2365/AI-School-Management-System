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
from backend.routes.imports import router as imports_router

# ✅ ERROR MONITORING (Sentry)
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
        print(f"✅ Sentry error monitoring enabled ({settings.SENTRY_ENVIRONMENT})")
    except Exception as _sentry_err:
        print(f"⚠️ Sentry init failed (continuing without it): {_sentry_err}")


# ✅ NON-DESTRUCTIVE AUTO-MIGRATION
def _ensure_columns(inspector, existing_tables: set[str], table_name: str, columns: dict[str, str]):
    if table_name not in existing_tables:
        return
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
        if settings.SENTRY_DSN:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
                sentry_sdk.flush(timeout=3)
            except Exception:
                pass
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
        )
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

        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # ==================== SCHOOLS ====================
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
            "fee_structure": "fee_structure TEXT",
            "fee_due_day": "fee_due_day INTEGER",
            "custom_fields": "custom_fields TEXT",
        })

        # ==================== ANNOUNCEMENTS ====================
        _ensure_columns(inspector, existing_tables, "announcements", {
            "audience": "audience VARCHAR(20) NOT NULL DEFAULT 'both'",
        })

        # ==================== STAFF ====================
        _ensure_columns(inspector, existing_tables, "staff", {
            "role": "role VARCHAR(20) NOT NULL DEFAULT 'teacher'",
            "user_id": "user_id INTEGER",
        })

        # ==================== STUDENTS ====================
        _ensure_columns(inspector, existing_tables, "students", {
            "photo_url": "photo_url VARCHAR(500)",
            "parent_email": "parent_email VARCHAR(150)",
            "parent_user_id": "parent_user_id INTEGER",
            # ✅ NEW (using FLOAT for cross-compatibility)
            "admission_date": "admission_date DATE",
            "b_form_number": "b_form_number VARCHAR(50)",
            "admission_fee": "admission_fee FLOAT",
            "monthly_fee_override": "monthly_fee_override FLOAT",
            "custom_fields_data": "custom_fields_data TEXT",
        })

        # ==================== USERS ====================
        _ensure_columns(inspector, existing_tables, "users", {
            "failed_login_attempts": "failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "locked_until": "locked_until TIMESTAMP",
        })

        # ==================== ATTENDANCE ====================
        _ensure_columns(inspector, existing_tables, "attendance", {
            "marked_by_user_id": "marked_by_user_id INTEGER",
            "is_locked": "is_locked BOOLEAN NOT NULL DEFAULT FALSE",
            "locked_at": "locked_at TIMESTAMP",
        })

        # ⚠️ SECURITY WARNINGS
        if settings.JWT_SECRET == "replace_with_a_strong_random_secret":
            print("🚨🚨🚨 SECURITY WARNING: JWT_SECRET is still the default placeholder! "
                  "Anyone can forge login tokens. Set a real random JWT_SECRET immediately.")
        if not settings.SUPER_ADMIN_SECRET:
            print("⚠️  SUPER_ADMIN_SECRET is not set — the super-admin panel route is unreachable "
                  "(fails closed), which is safe, but set it if you actually use that panel.")

        # Initialize all tables
        init_db()
        print("✅ Database tables created/verified")

        # Demo account — only in DEBUG mode
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
app.include_router(imports_router, tags=["imports"])
print("✅ Bulk import routes loaded")


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
    uptime pinger can hit this every few days and keep a free-tier Supabase
    project from auto-pausing due to inactivity.
    """
    db.execute(text("SELECT 1"))
    return {"status": "alive"}


@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"message": "OK"}


# ==================== SERVE FRONTEND ====================
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
    uvicorn.run(app, host="0.0.0.0", port=8000)from fastapi import FastAPI, Request, Depends
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
from backend.routes.imports import router as imports_router

# ✅ ERROR MONITORING (Sentry)
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
        print(f"✅ Sentry error monitoring enabled ({settings.SENTRY_ENVIRONMENT})")
    except Exception as _sentry_err:
        print(f"⚠️ Sentry init failed (continuing without it): {_sentry_err}")


# ✅ NON-DESTRUCTIVE AUTO-MIGRATION
def _ensure_columns(inspector, existing_tables: set[str], table_name: str, columns: dict[str, str]):
    if table_name not in existing_tables:
        return
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
        if settings.SENTRY_DSN:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
                sentry_sdk.flush(timeout=3)
            except Exception:
                pass
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"}
        )
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

        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # ==================== SCHOOLS ====================
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
            # ✅ NEW
            "fee_structure": "fee_structure TEXT",
            "fee_due_day": "fee_due_day INTEGER",
            "custom_fields": "custom_fields TEXT",
        })

        # ==================== ANNOUNCEMENTS ====================
        _ensure_columns(inspector, existing_tables, "announcements", {
            "audience": "audience VARCHAR(20) NOT NULL DEFAULT 'both'",
        })

        # ==================== STAFF ====================
        _ensure_columns(inspector, existing_tables, "staff", {
            "role": "role VARCHAR(20) NOT NULL DEFAULT 'teacher'",
            "user_id": "user_id INTEGER",
        })

        # ==================== STUDENTS ====================
        _ensure_columns(inspector, existing_tables, "students", {
            "photo_url": "photo_url VARCHAR(500)",
            "parent_email": "parent_email VARCHAR(150)",
            "parent_user_id": "parent_user_id INTEGER",
            # ✅ NEW (using FLOAT for cross-compatibility)
            "admission_date": "admission_date DATE",
            "b_form_number": "b_form_number VARCHAR(50)",
            "admission_fee": "admission_fee FLOAT",
            "monthly_fee_override": "monthly_fee_override FLOAT",
            "custom_fields_data": "custom_fields_data TEXT",
        })

        # ==================== USERS ====================
        _ensure_columns(inspector, existing_tables, "users", {
            "failed_login_attempts": "failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "locked_until": "locked_until TIMESTAMP",
        })

        # ==================== ATTENDANCE ====================
        _ensure_columns(inspector, existing_tables, "attendance", {
            "marked_by_user_id": "marked_by_user_id INTEGER",
            "is_locked": "is_locked BOOLEAN NOT NULL DEFAULT FALSE",
            "locked_at": "locked_at TIMESTAMP",
        })

        # ⚠️ SECURITY WARNINGS
        if settings.JWT_SECRET == "replace_with_a_strong_random_secret":
            print("🚨🚨🚨 SECURITY WARNING: JWT_SECRET is still the default placeholder! "
                  "Anyone can forge login tokens. Set a real random JWT_SECRET immediately.")
        if not settings.SUPER_ADMIN_SECRET:
            print("⚠️  SUPER_ADMIN_SECRET is not set — the super-admin panel route is unreachable "
                  "(fails closed), which is safe, but set it if you actually use that panel.")

        # Initialize all tables
        init_db()
        print("✅ Database tables created/verified")

        # Demo account — only in DEBUG mode
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
app.include_router(imports_router, tags=["imports"])
print("✅ Bulk import routes loaded")


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
    uptime pinger can hit this every few days and keep a free-tier Supabase
    project from auto-pausing due to inactivity.
    """
    db.execute(text("SELECT 1"))
    return {"status": "alive"}


@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return {"message": "OK"}


# ==================== SERVE FRONTEND ====================
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