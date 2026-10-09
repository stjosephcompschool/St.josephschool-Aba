#!/usr/bin/env python3
"""
Secondary School Portal - Streamlit Web App
Features:
- Student/Parent login
- View & download academic results (PDF)
- View school fees & Pay Now (Paystack-ready)
- Simple Admin panel
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from fpdf import FPDF
import hashlib
import os
from io import BytesIO

# ====================== CONFIG ======================
DB_PATH = "secondary_school.db"
ADMIN_PASSWORD = "admin123"          # Change this later
SCHOOL_NAME = "Greenfield Secondary School"
SCHOOL_MOTTO = "Excellence • Integrity • Service"

# Paystack (put your real keys in Streamlit Secrets later)
PAYSTACK_PUBLIC_KEY = "pk_test_xxxxxxxxxxxxxxxx"   # Replace with real key

# ====================== DATABASE ======================
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    """Create / upgrade database tables"""
    conn = get_connection()
    c = conn.cursor()

    # Students (keep existing if present)
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth DATE,
            gender TEXT,
            form_level TEXT NOT NULL,
            admission_year INTEGER,
            pin TEXT DEFAULT '1234'
        )
    """)

    # Migration: add pin column if the table already existed without it
    try:
        c.execute("ALTER TABLE students ADD COLUMN pin TEXT DEFAULT '1234'")
    except Exception:
        pass  # column already exists

    # Teachers
    c.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            hire_date DATE
        )
    """)

    # Subjects
    c.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL UNIQUE,
            subject_code TEXT UNIQUE,
            department TEXT
        )
    """)

    # Classes
    c.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            class_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            subject_id INTEGER,
            teacher_id INTEGER,
            academic_year TEXT,
            room TEXT,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        )
    """)

    # Enrollments
    c.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            class_id INTEGER,
            enrollment_date DATE DEFAULT CURRENT_DATE,
            UNIQUE(student_id, class_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id)
        )
    """)

    # Marks
    c.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER,
            term TEXT,
            score REAL,
            grade TEXT,
            remarks TEXT,
            FOREIGN KEY (enrollment_id) REFERENCES enrollments(enrollment_id)
        )
    """)

    # Fees
    c.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            term TEXT NOT NULL,
            amount_due REAL NOT NULL,
            amount_paid REAL DEFAULT 0,
            due_date DATE,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    # Payments
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            fee_id INTEGER,
            amount REAL,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            method TEXT,
            reference TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (fee_id) REFERENCES fees(fee_id)
        )
    """)

    conn.commit()
    conn.close()

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def seed_sample_data():
    """Insert sample data only if tables are empty"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students")
    has_students = c.fetchone()[0] > 0

    # Always ensure default PINs are hashed if needed
    default_hashed = hash_pin("1234")
    c.execute("UPDATE students SET pin = ? WHERE pin IS NULL OR pin = '1234' OR length(pin) < 20", (default_hashed,))

    # Seed fees if missing
    c.execute("SELECT COUNT(*) FROM fees")
    if c.fetchone()[0] == 0 and has_students:
        fees = []
        for sid in range(1, 9):
            fees.append((sid, "2025/2026", "Term 1", 85000.00, 0.0, "2025-10-15", "Pending"))
            fees.append((sid, "2025/2026", "Term 2", 85000.00, 0.0, "2026-01-15", "Pending"))
        c.executemany("""
            INSERT INTO fees (student_id, academic_year, term, amount_due, amount_paid, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, fees)
        c.execute("UPDATE fees SET amount_paid = 40000, status = 'Partial' WHERE student_id = 1 AND term = 'Term 1'")
        c.execute("UPDATE fees SET amount_paid = 85000, status = 'Paid' WHERE student_id = 5 AND term = 'Term 1'")
        conn.commit()

    if has_students:
        conn.close()
        return

    # Students with PINs (default PIN = 1234 for all)
    students = [
        ("Amina", "Okello", "2009-03-15", "F", "Form 3", 2023, hash_pin("1234")),
        ("Brian", "Mwangi", "2008-11-22", "M", "Form 4", 2022, hash_pin("1234")),
        ("Chioma", "Adeyemi", "2010-07-08", "F", "Form 2", 2024, hash_pin("1234")),
        ("David", "Ndlovu", "2009-01-30", "M", "Form 3", 2023, hash_pin("1234")),
        ("Elena", "Silva", "2008-05-12", "F", "Form 4", 2022, hash_pin("1234")),
        ("Farai", "Chikore", "2010-09-19", "M", "Form 2", 2024, hash_pin("1234")),
        ("Grace", "Mensah", "2009-12-03", "F", "Form 3", 2023, hash_pin("1234")),
        ("Hassan", "Ibrahim", "2008-08-25", "M", "Form 4", 2022, hash_pin("1234")),
    ]
    c.executemany("""
        INSERT INTO students (first_name, last_name, date_of_birth, gender, form_level, admission_year, pin)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, students)

    # Teachers
    teachers = [
        ("James", "Okafor", "j.okafor@school.edu", "+234-801-234-5678", "2018-09-01"),
        ("Sarah", "Bello", "s.bello@school.edu", "+234-802-345-6789", "2019-01-15"),
        ("Michael", "Kariuki", "m.kariuki@school.edu", "+254-712-456-789", "2017-08-20"),
        ("Fatima", "Hassan", "f.hassan@school.edu", "+234-803-567-8901", "2020-02-10"),
        ("Peter", "Van der Berg", "p.vanderberg@school.edu", "+27-82-678-9012", "2016-03-05"),
    ]
    c.executemany("""
        INSERT INTO teachers (first_name, last_name, email, phone, hire_date)
        VALUES (?, ?, ?, ?, ?)
    """, teachers)

    # Subjects
    subjects = [
        ("Mathematics", "MATH", "Sciences"),
        ("English Language", "ENG", "Languages"),
        ("Biology", "BIO", "Sciences"),
        ("Chemistry", "CHEM", "Sciences"),
        ("Physics", "PHY", "Sciences"),
        ("History", "HIST", "Humanities"),
        ("Geography", "GEO", "Humanities"),
        ("Computer Science", "CS", "Technology"),
    ]
    c.executemany("""
        INSERT INTO subjects (subject_name, subject_code, department)
        VALUES (?, ?, ?)
    """, subjects)

    # Classes
    classes = [
        ("Form 3A Mathematics", 1, 1, "2025/2026", "Room 12"),
        ("Form 3A English", 2, 2, "2025/2026", "Room 5"),
        ("Form 4 Science Biology", 3, 3, "2025/2026", "Lab 1"),
        ("Form 2 Mathematics", 1, 1, "2025/2026", "Room 8"),
        ("Form 4 Chemistry", 4, 4, "2025/2026", "Lab 2"),
        ("Form 3 History", 6, 5, "2025/2026", "Room 15"),
        ("Form 4 Physics", 5, 3, "2025/2026", "Lab 3"),
        ("Form 2 Computer Science", 8, 4, "2025/2026", "ICT Lab"),
    ]
    c.executemany("""
        INSERT INTO classes (class_name, subject_id, teacher_id, academic_year, room)
        VALUES (?, ?, ?, ?, ?)
    """, classes)

    # Enrollments
    enrollments = [
        (1, 1), (4, 1), (7, 1),
        (1, 2), (4, 2), (7, 2),
        (2, 3), (5, 3), (8, 3),
        (3, 4), (6, 4),
        (2, 5), (5, 5), (8, 5),
        (1, 6), (4, 6), (7, 6),
        (2, 7), (5, 7), (8, 7),
        (3, 8), (6, 8),
    ]
    c.executemany("INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)", enrollments)

    # Marks (Term 1)
    marks = [
        (1, "Term 1", 78.5, "B", "Good progress"),
        (2, "Term 1", 65.0, "C", None),
        (3, "Term 1", 91.0, "A", "Excellent"),
        (4, "Term 1", 82.0, "B", None),
        (5, "Term 1", 70.5, "C", "Needs improvement in writing"),
        (6, "Term 1", 88.0, "A", None),
        (7, "Term 1", 74.0, "B", None),
        (8, "Term 1", 95.5, "A", "Outstanding"),
        (9, "Term 1", 68.0, "C", None),
        (10, "Term 1", 55.0, "D", "Requires extra support"),
        (11, "Term 1", 80.0, "B", None),
        (12, "Term 1", 72.5, "B", None),
        (13, "Term 1", 89.0, "A", None),
        (14, "Term 1", 61.0, "C", None),
        (15, "Term 1", 77.0, "B", None),
        (16, "Term 1", 84.5, "B", None),
        (17, "Term 1", 69.0, "C", None),
        (18, "Term 1", 86.0, "A", None),
        (19, "Term 1", 79.5, "B", None),
        (20, "Term 1", 92.0, "A", "Top performer"),
        (21, "Term 1", 90.0, "A", None),
        (22, "Term 1", 75.0, "B", None),
    ]
    c.executemany("""
        INSERT INTO marks (enrollment_id, term, score, grade, remarks)
        VALUES (?, ?, ?, ?, ?)
    """, marks)

    # Fees for all students (2025/2026 Term 1)
    fees = []
    for sid in range(1, 9):
        fees.append((sid, "2025/2026", "Term 1", 85000.00, 0.0, "2025-10-15", "Pending"))
        fees.append((sid, "2025/2026", "Term 2", 85000.00, 0.0, "2026-01-15", "Pending"))
    c.executemany("""
        INSERT INTO fees (student_id, academic_year, term, amount_due, amount_paid, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, fees)

    # Make some partial payments for demo
    c.execute("UPDATE fees SET amount_paid = 40000, status = 'Partial' WHERE student_id = 1 AND term = 'Term 1'")
    c.execute("UPDATE fees SET amount_paid = 85000, status = 'Paid' WHERE student_id = 5 AND term = 'Term 1'")

    conn.commit()
    conn.close()

# ====================== HELPERS ======================
def get_student_by_id(student_id: int):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM students WHERE student_id = ?",
        conn, params=(student_id,)
    )
    conn.close()
    return df.iloc[0] if not df.empty else None

def authenticate_student(student_id: int, pin: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT pin FROM students WHERE student_id = ?", (student_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == hash_pin(pin):
        return True
    return False

def get_student_results(student_id: int):
    conn = get_connection()
    query = """
        SELECT 
            s.subject_name,
            c.class_name,
            m.term,
            m.score,
            m.grade,
            m.remarks
        FROM marks m
        JOIN enrollments e ON m.enrollment_id = e.enrollment_id
        JOIN classes c ON e.class_id = c.class_id
        JOIN subjects s ON c.subject_id = s.subject_id
        WHERE e.student_id = ?
        ORDER BY m.term, s.subject_name
    """
    df = pd.read_sql_query(query, conn, params=(student_id,))
    conn.close()
    return df

def get_student_fees(student_id: int):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT fee_id, academic_year, term, amount_due, amount_paid,
               (amount_due - amount_paid) AS balance, due_date, status
        FROM fees
        WHERE student_id = ?
        ORDER BY academic_year, term
        """,
        conn, params=(student_id,)
    )
    conn.close()
    return df

def generate_results_pdf(student, results_df):
    """Generate a clean PDF report card"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, SCHOOL_NAME, ln=True, align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, SCHOOL_MOTTO, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "ACADEMIC REPORT CARD", ln=True, align="C")
    pdf.ln(5)

    # Student info
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Student Name : {student['first_name']} {student['last_name']}", ln=True)
    pdf.cell(0, 7, f"Student ID   : {student['student_id']}", ln=True)
    pdf.cell(0, 7, f"Form Level   : {student['form_level']}", ln=True)
    pdf.cell(0, 7, f"Academic Year: 2025/2026", ln=True)
    pdf.ln(5)

    # Table header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(40, 80, 140)
    pdf.set_text_color(255, 255, 255)
    col_widths = [55, 35, 25, 25, 45]
    headers = ["Subject", "Term", "Score", "Grade", "Remarks"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    fill = False
    for _, row in results_df.iterrows():
        if fill:
            pdf.set_fill_color(240, 240, 240)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(col_widths[0], 7, str(row["subject_name"])[:28], border=1, fill=True)
        pdf.cell(col_widths[1], 7, str(row["term"]), border=1, fill=True, align="C")
        pdf.cell(col_widths[2], 7, f"{row['score']:.1f}", border=1, fill=True, align="C")
        pdf.cell(col_widths[3], 7, str(row["grade"]), border=1, fill=True, align="C")
        remarks = str(row["remarks"]) if pd.notna(row["remarks"]) else ""
        pdf.cell(col_widths[4], 7, remarks[:22], border=1, fill=True)
        pdf.ln()
        fill = not fill

    # Average
    if not results_df.empty:
        avg = results_df["score"].mean()
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Average Score: {avg:.1f}%", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Generated on {datetime.now().strftime('%d %B %Y at %H:%M')}", ln=True)
    pdf.cell(0, 5, "This is a computer-generated document.", ln=True)

    return pdf.output()

# ====================== PAGES ======================
def login_page():
    st.title(f"🎓 {SCHOOL_NAME}")
    st.markdown(f"*{SCHOOL_MOTTO}*")
    st.markdown("---")

    tab1, tab2 = st.tabs(["👨‍🎓 Student / Parent Login", "🔐 Admin Login"])

    with tab1:
        st.subheader("Student / Parent Portal")
        st.info("Demo PINs: All students use PIN **1234**")

        col1, col2 = st.columns(2)
        with col1:
            student_id = st.number_input("Student ID", min_value=1, step=1, value=1)
        with col2:
            pin = st.text_input("PIN", type="password", value="1234")

        if st.button("Login as Student/Parent", type="primary", use_container_width=True):
            if authenticate_student(int(student_id), pin):
                st.session_state["logged_in"] = True
                st.session_state["role"] = "student"
                st.session_state["student_id"] = int(student_id)
                st.rerun()
            else:
                st.error("Invalid Student ID or PIN")

    with tab2:
        st.subheader("Administrator Login")
        admin_pass = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin", type="primary", use_container_width=True):
            if admin_pass == ADMIN_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["role"] = "admin"
                st.rerun()
            else:
                st.error("Incorrect password")

def student_dashboard():
    student_id = st.session_state["student_id"]
    student = get_student_by_id(student_id)

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["🏠 Dashboard", "📊 My Results", "💰 School Fees", "🚪 Logout"]
    )

    st.sidebar.markdown("---")
    st.sidebar.write(f"**Logged in as:**")
    st.sidebar.write(f"{student['first_name']} {student['last_name']}")
    st.sidebar.write(f"ID: {student_id} | {student['form_level']}")

    if page == "🚪 Logout":
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    elif page == "🏠 Dashboard":
        st.title(f"Welcome, {student['first_name']}! 👋")
        st.markdown(f"**Form:** {student['form_level']} &nbsp;&nbsp;|&nbsp;&nbsp; **Student ID:** {student_id}")

        col1, col2, col3 = st.columns(3)
        results = get_student_results(student_id)
        fees = get_student_fees(student_id)
        total_balance = fees["balance"].sum() if not fees.empty else 0
        avg_score = results["score"].mean() if not results.empty else 0

        col1.metric("Average Score", f"{avg_score:.1f}%")
        col2.metric("Subjects Taken", len(results))
        col3.metric("Outstanding Fees", f"₦{total_balance:,.0f}")

        st.markdown("---")
        st.subheader("Quick Actions")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊 View Results", use_container_width=True):
                st.session_state["force_page"] = "📊 My Results"
                st.rerun()
        with c2:
            if st.button("💰 Pay School Fees", use_container_width=True):
                st.session_state["force_page"] = "💰 School Fees"
                st.rerun()

    elif page == "📊 My Results":
        st.title("📊 My Academic Results")
        results = get_student_results(student_id)

        if results.empty:
            st.warning("No results available yet.")
        else:
            st.dataframe(
                results.rename(columns={
                    "subject_name": "Subject",
                    "class_name": "Class",
                    "term": "Term",
                    "score": "Score (%)",
                    "grade": "Grade",
                    "remarks": "Remarks"
                }),
                use_container_width=True,
                hide_index=True
            )

            avg = results["score"].mean()
            st.success(f"**Overall Average: {avg:.1f}%**")

            # PDF Download
            pdf_bytes = generate_results_pdf(student, results)
            st.download_button(
                label="📥 Download Report Card (PDF)",
                data=pdf_bytes,
                file_name=f"ReportCard_{student['last_name']}_{student_id}.pdf",
                mime="application/pdf",
                type="primary"
            )

    elif page == "💰 School Fees":
        st.title("💰 School Fees")
        fees = get_student_fees(student_id)

        if fees.empty:
            st.info("No fee records found.")
        else:
            # Summary
            total_due = fees["amount_due"].sum()
            total_paid = fees["amount_paid"].sum()
            total_balance = fees["balance"].sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Due", f"₦{total_due:,.0f}")
            c2.metric("Total Paid", f"₦{total_paid:,.0f}")
            c3.metric("Outstanding Balance", f"₦{total_balance:,.0f}")

            st.markdown("---")
            st.subheader("Fee Breakdown")

            display_fees = fees.copy()
            display_fees["amount_due"] = display_fees["amount_due"].apply(lambda x: f"₦{x:,.0f}")
            display_fees["amount_paid"] = display_fees["amount_paid"].apply(lambda x: f"₦{x:,.0f}")
            display_fees["balance"] = display_fees["balance"].apply(lambda x: f"₦{x:,.0f}")

            st.dataframe(
                display_fees[["academic_year", "term", "amount_due", "amount_paid", "balance", "due_date", "status"]],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("💳 Pay Outstanding Fees")

            outstanding = fees[fees["balance"] > 0]
            if outstanding.empty:
                st.success("🎉 All fees are fully paid. Thank you!")
            else:
                selected_fee = st.selectbox(
                    "Select term to pay",
                    options=outstanding["fee_id"].tolist(),
                    format_func=lambda x: f"{outstanding[outstanding['fee_id']==x]['term'].values[0]} "
                                          f"({outstanding[outstanding['fee_id']==x]['academic_year'].values[0]}) - "
                                          f"Balance: ₦{outstanding[outstanding['fee_id']==x]['balance'].values[0]:,.0f}"
                )

                fee_row = outstanding[outstanding["fee_id"] == selected_fee].iloc[0]
                balance = fee_row["balance"]

                st.write(f"**Amount to pay:** ₦{balance:,.0f}")

                # Payment simulation / Paystack ready
                st.info(
                    "In a live system this button opens Paystack checkout.\n\n"
                    "For now, this is a **demo**. Click below to simulate a successful payment."
                )

                if st.button(f"💳 Pay ₦{balance:,.0f} Now", type="primary", use_container_width=True):
                    # Simulate successful payment
                    conn = get_connection()
                    c = conn.cursor()
                    new_paid = fee_row["amount_paid"] + balance
                    new_status = "Paid" if new_paid >= fee_row["amount_due"] else "Partial"
                    c.execute(
                        "UPDATE fees SET amount_paid = ?, status = ? WHERE fee_id = ?",
                        (new_paid, new_status, selected_fee)
                    )
                    c.execute(
                        """INSERT INTO payments (student_id, fee_id, amount, method, reference, status)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (student_id, selected_fee, balance, "Demo/Paystack", f"DEMO-{datetime.now().strftime('%Y%m%d%H%M%S')}", "Successful")
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Payment of ₦{balance:,.0f} recorded successfully!")
                    st.balloons()
                    st.rerun()

                st.markdown("---")
                st.caption(
                    "🔧 **To go live with real payments:**\n"
                    "1. Create a free Paystack account\n"
                    "2. Put your Public Key in Streamlit Secrets\n"
                    "3. Replace the demo button with Paystack Inline or Redirect"
                )

def admin_dashboard():
    st.sidebar.title("Admin Panel")
    page = st.sidebar.radio(
        "Go to",
        ["📊 Overview", "👨‍🎓 Students", "💰 Fees & Payments", "🚪 Logout"]
    )

    if page == "🚪 Logout":
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.title("🔐 Administrator Dashboard")

    conn = get_connection()

    if page == "📊 Overview":
        students = pd.read_sql_query("SELECT COUNT(*) as cnt FROM students", conn).iloc[0]["cnt"]
        pending_fees = pd.read_sql_query(
            "SELECT SUM(amount_due - amount_paid) as bal FROM fees WHERE status != 'Paid'", conn
        ).iloc[0]["bal"] or 0
        paid_this_term = pd.read_sql_query(
            "SELECT SUM(amount_paid) as paid FROM fees WHERE term = 'Term 1'", conn
        ).iloc[0]["paid"] or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Students", students)
        c2.metric("Outstanding Fees", f"₦{pending_fees:,.0f}")
        c3.metric("Collected (Term 1)", f"₦{paid_this_term:,.0f}")

        st.subheader("Recent Payments")
        payments = pd.read_sql_query("""
            SELECT p.payment_date, s.first_name || ' ' || s.last_name as student,
                   p.amount, p.method, p.reference, p.status
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            ORDER BY p.payment_date DESC LIMIT 10
        """, conn)
        if not payments.empty:
            st.dataframe(payments, use_container_width=True, hide_index=True)
        else:
            st.info("No payments recorded yet.")

    elif page == "👨‍🎓 Students":
        st.subheader("All Students")
        df = pd.read_sql_query("""
            SELECT student_id, first_name, last_name, form_level, gender, admission_year
            FROM students ORDER BY form_level, last_name
        """, conn)
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif page == "💰 Fees & Payments":
        st.subheader("Fee Status Overview")
        fees = pd.read_sql_query("""
            SELECT s.student_id, s.first_name || ' ' || s.last_name as student,
                   s.form_level, f.term, f.amount_due, f.amount_paid,
                   (f.amount_due - f.amount_paid) as balance, f.status
            FROM fees f
            JOIN students s ON f.student_id = s.student_id
            ORDER BY balance DESC
        """, conn)
        st.dataframe(fees, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Manually Mark Fee as Paid")
        with st.form("mark_paid"):
            fee_id = st.number_input("Fee ID", min_value=1, step=1)
            amount = st.number_input("Amount Paid", min_value=0.0, step=1000.0)
            if st.form_submit_button("Update Payment"):
                c = conn.cursor()
                c.execute("SELECT amount_due, amount_paid FROM fees WHERE fee_id = ?", (fee_id,))
                row = c.fetchone()
                if row:
                    new_paid = row[1] + amount
                    status = "Paid" if new_paid >= row[0] else "Partial"
                    c.execute("UPDATE fees SET amount_paid = ?, status = ? WHERE fee_id = ?",
                              (new_paid, status, fee_id))
                    conn.commit()
                    st.success("Updated successfully!")
                    st.rerun()
                else:
                    st.error("Fee ID not found")

    conn.close()

# ====================== MAIN ======================
def main():
    st.set_page_config(
        page_title=f"{SCHOOL_NAME} Portal",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS
    st.markdown("""
        <style>
        .stButton>button {
            border-radius: 8px;
        }
        .main-header {
            font-size: 2rem;
            font-weight: 700;
            color: #1a365d;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize
    init_db()
    seed_sample_data()

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login_page()
    else:
        if st.session_state["role"] == "student":
            student_dashboard()
        else:
            admin_dashboard()

if __name__ == "__main__":
    main()
