from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import hashlib
import json
import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv


# ==========================================
# LOAD .ENV
# ==========================================

load_dotenv(Path(__file__).with_name(".env"))


# ==========================================
# VYOMIX FASTAPI BACKEND
# ==========================================

app = FastAPI(title="VYOMIX Backend")


# ==========================================
# CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# DATABASE
# ==========================================

DATABASE = str(Path(__file__).with_name("vyomix.db"))


def create_database():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            module TEXT NOT NULL,
            total_components INTEGER NOT NULL DEFAULT 0,
            normal_count INTEGER NOT NULL DEFAULT 0,
            anomaly_count INTEGER NOT NULL DEFAULT 0,
            prediction_count INTEGER NOT NULL DEFAULT 0,
            high_risk_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            component_id TEXT NOT NULL,
            status TEXT,
            score REAL,
            explanation TEXT,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screening_id TEXT,
            user_email TEXT NOT NULL,
            filename TEXT NOT NULL,
            total_components INTEGER NOT NULL DEFAULT 0,
            pass_count INTEGER NOT NULL DEFAULT 0,
            monitor_count INTEGER NOT NULL DEFAULT 0,
            reject_count INTEGER NOT NULL DEFAULT 0,
            module_a_anomaly_count INTEGER NOT NULL DEFAULT 0,
            module_b_at_risk_count INTEGER NOT NULL DEFAULT 0,
            review_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            module_a_json TEXT NOT NULL DEFAULT '[]',
            module_b_json TEXT NOT NULL DEFAULT '[]',
            final_results_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'Completed',
            created_at TEXT NOT NULL
        )
    """)

    existing_columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(screenings)").fetchall()
    }
    migration_columns = {
        "screening_id": "TEXT",
        "module_a_anomaly_count": "INTEGER NOT NULL DEFAULT 0",
        "module_b_at_risk_count": "INTEGER NOT NULL DEFAULT 0",
        "review_count": "INTEGER NOT NULL DEFAULT 0",
        "failed_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for column, definition in migration_columns.items():
        if column not in existing_columns:
            cursor.execute(
                f"ALTER TABLE screenings ADD COLUMN {column} {definition}"
            )

    conn.commit()
    conn.close()


create_database()


# ==========================================
# PASSWORD HASHING
# ==========================================

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# ==========================================
# OTP STORAGE
# ==========================================

otp_storage = {}


# ==========================================
# GENERATE OTP
# ==========================================

def generate_otp():

    return str(
        random.randint(100000, 999999)
    )


# ==========================================
# SEND OTP EMAIL
# ==========================================

def send_otp_email(receiver_email, otp):

    # Get VYOMIX sender email from .env
    smtp_email = os.getenv("SMTP_EMAIL")

    # Get Gmail App Password from .env
    smtp_password = os.getenv("SMTP_APP_PASSWORD")


    # Check credentials
    if not smtp_email or not smtp_password:

        print("ERROR: SMTP credentials are missing.")

        return False


    # Create email
    message = EmailMessage()

    message["Subject"] = "Your VYOMIX Login OTP"

    message["From"] = smtp_email

    message["To"] = receiver_email


    # Email content
    message.set_content(f"""
VYOMIX LOGIN VERIFICATION
==========================

Hello,

Your One-Time Password (OTP) for logging into VYOMIX is:

{otp}

This OTP is valid for 5 minutes.

If you did not request this OTP, please ignore this email.

Regards,
VYOMIX Security Team
""")


    try:

        # Connect to Gmail
        with smtplib.SMTP(
            "smtp.gmail.com",
            587
        ) as server:

            # Secure connection
            server.starttls()

            # Login using .env credentials
            server.login(
                smtp_email,
                smtp_password
            )

            # Send email
            server.send_message(message)


        print(
            f"OTP sent successfully to {receiver_email}"
        )

        return True


    except Exception as error:

        print(
            "Email sending error:",
            error
        )

        return False


# ==========================================
# REQUEST MODELS
# ==========================================

class SignupRequest(BaseModel):

    name: str

    employee_id: str

    email: str

    password: str

    role: str


class LoginRequest(BaseModel):

    login_id: str

    password: str


class OTPRequest(BaseModel):

    email: str


class VerifyOTPRequest(BaseModel):

    email: str

    otp: str


class AnalysisResult(BaseModel):

    component_id: str = ""

    status: str = ""

    score: float | None = None

    explanation: str = ""


class AnalysisRunRequest(BaseModel):

    user_email: str

    module: str

    total_components: int = 0

    normal_count: int = 0

    anomaly_count: int = 0

    prediction_count: int = 0

    high_risk_count: int = 0

    results: list[AnalysisResult] = []


class ScreeningResult(BaseModel):

    component_id: str = ""

    module_a: dict = {}

    module_b: dict = {}

    status: str = ""

    score: float | None = None

    explanation: str = ""

    module_a_explanation: str = ""

    module_b_explanation: str = ""

    reason: str = ""


class ScreeningRequest(BaseModel):

    screening_id: str | None = None

    user_email: str

    filename: str = "screening.csv"

    total_components: int = 0

    pass_count: int = 0

    monitor_count: int = 0

    reject_count: int = 0

    module_a_anomaly_count: int = 0

    module_b_at_risk_count: int = 0

    review_count: int = 0

    failed_count: int = 0

    module_a: list[dict] = []

    module_b: list[dict] = []

    results: list[ScreeningResult] = []


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():

    return {
        "success": True,
        "message": "VYOMIX Backend is running 🚀"
    }


# ==========================================
# SIGN UP
# ==========================================

@app.post("/signup")
def signup(user: SignupRequest):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    email = user.email.strip().lower()


    # Hash password
    password_hash = hash_password(
        user.password
    )


    try:

        cursor.execute("""
            INSERT INTO users
            (
                name,
                employee_id,
                email,
                password,
                role
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user.name,
            user.employee_id,
            email,
            password_hash,
            user.role
        ))


        conn.commit()


        return {
            "success": True,
            "message": "Account created successfully",
            "email": email
        }


    except sqlite3.IntegrityError:

        return {
            "success": False,
            "message":
                "Employee ID or email already exists"
        }


    finally:

        conn.close()


# ==========================================
# LOGIN
# ==========================================

@app.post("/login")
def login(user: LoginRequest):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    login_id = user.login_id.strip()
    if "@" in login_id:
        login_id = login_id.lower()


    # Hash entered password
    password_hash = hash_password(
        user.password
    )


    # Find user
    cursor.execute("""
        SELECT
            id,
            name,
            employee_id,
            email,
            role
        FROM users
        WHERE
            (email = ? OR employee_id = ?)
            AND password = ?
    """, (
        login_id,
        login_id,
        password_hash
    ))


    result = cursor.fetchone()


    # User found
    if result:

        conn.close()

        return {

            "success": True,

            "message":
                "Login successful",

            "user": {

                "id": result[0],

                "name": result[1],

                "employee_id": result[2],

                "email": result[3],

                "role": result[4]

            }

        }


    cursor = conn.cursor()
    cursor.execute(
        "SELECT email FROM users WHERE email = ? OR employee_id = ?",
        (login_id, login_id)
    )
    account_exists = cursor.fetchone() is not None

    conn.close()

    if not account_exists:
        return {
            "success": False,
            "message": "Email address or employee ID is not registered"
        }

    return {

        "success": False,

        "message":
            "Incorrect password"

    }


# ==========================================
# SEND OTP
# ==========================================

@app.post("/send-otp")
def send_otp(request: OTPRequest):

    email = request.email.strip()


    # --------------------------------------
    # CHECK USER EXISTS
    # --------------------------------------

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()


    cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    )


    user = cursor.fetchone()

    conn.close()


    if not user:

        return {

            "success": False,

            "message":
                "Email address is not registered"

        }


    # --------------------------------------
    # GENERATE OTP
    # --------------------------------------

    otp = generate_otp()


    # --------------------------------------
    # CREATE EXPIRY TIME
    # --------------------------------------

    expiry_time = (
        datetime.now()
        + timedelta(minutes=5)
    )


    # --------------------------------------
    # STORE OTP
    # --------------------------------------

    otp_storage[email] = {

        "otp": otp,

        "expires_at":
            expiry_time

    }


    # --------------------------------------
    # SEND EMAIL
    # --------------------------------------

    email_sent = send_otp_email(
        email,
        otp
    )


    # --------------------------------------
    # EMAIL SENT
    # --------------------------------------

    if email_sent:

        return {

            "success": True,

            "message":
                "OTP sent successfully",

            "email":
                email

        }


    # --------------------------------------
    # EMAIL FAILED
    # --------------------------------------

    # Remove OTP if email could not be sent
    if email in otp_storage:

        del otp_storage[email]


    return {

        "success": False,

        "message":
            "Unable to send OTP email"

    }


# ==========================================
# VERIFY OTP
# ==========================================

@app.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest):

    email = request.email.strip()

    entered_otp = request.otp.strip()


    # --------------------------------------
    # CHECK OTP EXISTS
    # --------------------------------------

    if email not in otp_storage:

        return {

            "success": False,

            "message":
                "No OTP found. Please request a new OTP."

        }


    # Get stored OTP
    stored_data = otp_storage[email]


    stored_otp = stored_data["otp"]

    expiry_time = stored_data["expires_at"]


    # --------------------------------------
    # CHECK EXPIRY
    # --------------------------------------

    if datetime.now() > expiry_time:

        del otp_storage[email]

        return {

            "success": False,

            "message":
                "OTP has expired. Please request a new OTP."

        }


    # --------------------------------------
    # CHECK OTP
    # --------------------------------------

    if entered_otp != stored_otp:

        return {

            "success": False,

            "message":
                "Invalid OTP. Please try again."

        }


    # --------------------------------------
    # OTP CORRECT
    # --------------------------------------

    del otp_storage[email]


    return {

        "success": True,

        "message":
            "OTP verified successfully"

    }


# ==========================================
# ANALYSIS STORAGE
# ==========================================

@app.post("/analysis-runs")
def save_analysis_run(run: AnalysisRunRequest):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    created_at = datetime.now().isoformat(timespec="seconds")

    cursor.execute("""
        INSERT INTO analysis_runs (
            user_email, module, total_components, normal_count,
            anomaly_count, prediction_count, high_risk_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run.user_email,
        run.module,
        run.total_components,
        run.normal_count,
        run.anomaly_count,
        run.prediction_count,
        run.high_risk_count,
        created_at
    ))

    run_id = cursor.lastrowid

    cursor.executemany("""
        INSERT INTO analysis_results (
            run_id, component_id, status, score, explanation
        ) VALUES (?, ?, ?, ?, ?)
    """, [
        (
            run_id,
            result.component_id,
            result.status,
            result.score,
            result.explanation
        )
        for result in run.results
    ])

    conn.commit()
    conn.close()

    return {
        "success": True,
        "run_id": run_id,
        "created_at": created_at
    }


@app.get("/analysis-summary")
def analysis_summary(user_email: str):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(SUM(total_components), 0),
            COALESCE(SUM(normal_count), 0),
            COALESCE(SUM(anomaly_count), 0),
            COALESCE(SUM(prediction_count), 0),
            COALESCE(SUM(high_risk_count), 0),
            COUNT(*)
        FROM analysis_runs
        WHERE user_email = ?
    """, (user_email,))
    values = cursor.fetchone()
    conn.close()

    return {
        "success": True,
        "total_components": values[0],
        "normal_count": values[1],
        "anomaly_count": values[2],
        "prediction_count": values[3],
        "high_risk_count": values[4],
        "run_count": values[5]
    }


@app.get("/analysis-runs")
def analysis_runs(user_email: str):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, module, total_components, anomaly_count,
               prediction_count, high_risk_count, created_at
        FROM analysis_runs
        WHERE user_email = ?
        ORDER BY id DESC
    """, (user_email,))
    rows = cursor.fetchall()
    conn.close()

    return {
        "success": True,
        "runs": [
            {
                "screeningId": f"RUN-{row[0]:05d}",
                "module": row[1],
                "components": row[2],
                "anomalies": row[3] + row[5],
                "status": "Anomaly" if row[3] + row[5] else "Normal",
                "date": row[6]
            }
            for row in rows
        ]
    }


# ==========================================
# COMPLETED SCREENINGS
# ==========================================

@app.post("/screenings")
def save_screening(screening: ScreeningRequest):

    created_at = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    requested_id = screening.screening_id
    existing = None
    if requested_id:
        cursor.execute(
            "SELECT id FROM screenings WHERE screening_id = ?",
            (requested_id,)
        )
        existing = cursor.fetchone()

    result_json = json.dumps(
        [result.model_dump() for result in screening.results]
    )

    values = (
        screening.user_email,
        screening.filename,
        screening.total_components,
        screening.pass_count,
        screening.monitor_count,
        screening.reject_count,
        screening.module_a_anomaly_count,
        screening.module_b_at_risk_count,
        screening.review_count,
        screening.failed_count,
        json.dumps(screening.module_a),
        json.dumps(screening.module_b),
        result_json,
        "Completed",
        created_at
    )

    if existing:
        cursor.execute("""
            UPDATE screenings SET
                user_email = ?, filename = ?, total_components = ?,
                pass_count = ?, monitor_count = ?, reject_count = ?,
                module_a_anomaly_count = ?, module_b_at_risk_count = ?,
                review_count = ?, failed_count = ?, module_a_json = ?,
                module_b_json = ?, final_results_json = ?, status = ?,
                created_at = ?
            WHERE id = ?
        """, values + (existing[0],))
        database_id = existing[0]
    else:
        cursor.execute("""
            INSERT INTO screenings (
                user_email, filename, total_components, pass_count,
                monitor_count, reject_count, module_a_anomaly_count,
                module_b_at_risk_count, review_count, failed_count,
                module_a_json, module_b_json, final_results_json,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
        database_id = cursor.lastrowid

        generated_id = requested_id or f"SCR-{database_id:05d}"
        cursor.execute(
            "UPDATE screenings SET screening_id = ? WHERE id = ?",
            (generated_id, database_id)
        )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "screening_id": requested_id or f"SCR-{database_id:05d}",
        "created_at": created_at
    }


def screening_row(row):

    module_a = json.loads(row[11] or "[]")
    module_b = json.loads(row[12] or "[]")
    results = json.loads(row[13] or "[]")
    module_a_by_id = {item.get("component_id"): item for item in module_a}
    module_b_by_id = {item.get("component_id"): item for item in module_b}

    normalized_results = []
    for result in results:
        component_id = result.get("component_id")
        normalized = dict(result)
        normalized["module_a"] = {
            **module_a_by_id.get(component_id, {}),
            **(result.get("module_a") or {})
        }
        normalized["module_b"] = {
            **module_b_by_id.get(component_id, {}),
            **(result.get("module_b") or {})
        }
        normalized_results.append(normalized)

    return {
        "screeningId": row[1] or f"SCR-{row[0]:05d}",
        "filename": row[2],
        "components": row[3],
        "passCount": row[4],
        "monitorCount": row[5],
        "rejectCount": row[6],
        "moduleAAnomalies": row[7],
        "moduleBAtRisk": row[8],
        "reviewCount": row[9],
        "failedCount": row[10],
        "anomalies": row[7],
        "atRisk": row[8],
        "status": "REJECTED / FAIL" if row[6] else "REVIEW / AT-RISK" if row[5] else "ACCEPTED / PASS",
        "date": row[15],
        "moduleA": module_a,
        "moduleB": module_b,
        "results": normalized_results
    }


def screening_component_lists(rows):

    lists = {
        "total": [],
        "accepted": [],
        "module_a_anomalies": [],
        "module_b_at_risk": [],
        "review": [],
        "rejected": []
    }

    for row in rows:
        screening_id = row[1] or f"SCR-{row[0]:05d}"
        results = json.loads(row[13] or "[]")
        for result in results:
            module_a = result.get("module_a") or {}
            module_b = result.get("module_b") or {}
            raw_status = result.get("status", "")
            status = (
                "ACCEPTED / PASS" if raw_status in ("ACCEPTED / PASS", "PASS / NORMAL")
                else "REVIEW / AT-RISK" if raw_status in ("REVIEW / AT-RISK", "REVIEW")
                else "REJECTED / FAIL" if raw_status in ("REJECTED / FAIL", "FAIL / HIGH RISK")
                else raw_status
            )
            item = {
                "screening_id": screening_id,
                "component_id": result.get("component_id", ""),
                "lot_batch": module_a.get("lot_batch") or module_b.get("lot_batch") or "-",
                "status": status,
                "reason": result.get("reason") or result.get("explanation", ""),
                "module_a_status": module_a.get("status", ""),
                "module_a_score": module_a.get("score", module_a.get("anomaly_score")),
                "module_a_threshold": module_a.get("threshold"),
                "module_b_risk": module_b.get("risk", ""),
                "module_b_prediction": (module_b.get("predictions") or {}).get("RDSon_mOhm_168h"),
                "module_b_drift": (module_b.get("measurements") or {}).get("drift")
            }
            lists["total"].append(item)

            if result.get("status") in ("ACCEPTED / PASS", "PASS / NORMAL"):
                lists["accepted"].append(item)
            elif result.get("status") in ("REVIEW / AT-RISK", "REVIEW"):
                lists["review"].append(item)
            elif result.get("status") in ("REJECTED / FAIL", "FAIL / HIGH RISK"):
                lists["rejected"].append(item)

            if module_a.get("status") == "Anomaly":
                lists["module_a_anomalies"].append(item)
            if module_b.get("risk") in ("High", "Review"):
                lists["module_b_at_risk"].append(item)

    return lists


@app.get("/screenings")
def screenings(user_email: str):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
         SELECT id, screening_id, filename, total_components, pass_count,
             monitor_count, reject_count, module_a_anomaly_count,
             module_b_at_risk_count, review_count, failed_count,
             module_a_json, module_b_json, final_results_json,
             status, created_at
        FROM screenings
        WHERE user_email = ?
        ORDER BY id DESC
    """, (user_email,))
    rows = cursor.fetchall()
    conn.close()

    return {
        "success": True,
        "screenings": [screening_row(row) for row in rows]
    }


@app.get("/screenings/summary")
def screenings_summary(user_email: str):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(SUM(total_components), 0),
            COALESCE(SUM(pass_count), 0),
            COALESCE(SUM(monitor_count), 0),
            COALESCE(SUM(reject_count), 0),
            COALESCE(SUM(module_a_anomaly_count), 0),
            COALESCE(SUM(module_b_at_risk_count), 0),
            COALESCE(SUM(review_count), 0),
            COALESCE(SUM(failed_count), 0),
            COUNT(*)
        FROM screenings
        WHERE user_email = ?
    """, (user_email,))
    (
        total,
        passed,
        monitored,
        rejected,
        module_a_anomalies,
        module_b_at_risk,
        review_count,
        failed_count,
        count
    ) = cursor.fetchone()

    cursor.execute("""
        SELECT id, screening_id, filename, total_components, pass_count,
               monitor_count, reject_count, module_a_anomaly_count,
               module_b_at_risk_count, review_count, failed_count,
               module_a_json, module_b_json, final_results_json,
               status, created_at
        FROM screenings
        WHERE user_email = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_email,))
    latest_row = cursor.fetchone()

    cursor.execute("""
        SELECT id, screening_id, filename, total_components, pass_count,
               monitor_count, reject_count, module_a_anomaly_count,
               module_b_at_risk_count, review_count, failed_count,
               module_a_json, module_b_json, final_results_json,
               status, created_at
        FROM screenings
        WHERE user_email = ?
        ORDER BY id DESC
    """, (user_email,))
    all_rows = cursor.fetchall()
    conn.close()

    return {
        "success": True,
        "total_components": total,
        "pass_count": passed,
        "monitor_count": monitored,
        "reject_count": rejected,
        "module_a_anomaly_count": module_a_anomalies,
        "module_b_at_risk_count": module_b_at_risk,
        "review_count": review_count,
        "failed_count": failed_count,
        "screening_count": count,
        "latest_screening": screening_row(latest_row) if latest_row else None,
        "component_lists": screening_component_lists(all_rows)
    }


@app.get("/screenings/{screening_id}")
def screening_detail(screening_id: str, user_email: str):

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, screening_id, filename, total_components, pass_count,
               monitor_count, reject_count, module_a_anomaly_count,
               module_b_at_risk_count, review_count, failed_count,
               module_a_json, module_b_json, final_results_json,
               status, created_at
        FROM screenings
        WHERE screening_id = ? AND user_email = ?
    """, (screening_id, user_email))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {"success": False, "message": "Screening was not found."}

    return {"success": True, "screening": screening_row(row)}