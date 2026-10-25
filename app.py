from flask import Flask, render_template, request, redirect, session, send_from_directory
from config import cursor, db

import os
import re
from datetime import datetime, date

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename


# =========================================================
# TESSERACT
# =========================================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

print("App Started")

app = Flask(__name__)
app.secret_key = "smartcitizen360"


# =========================================================
# UPLOAD FOLDER
# =========================================================

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Profile Picture Folder
PROFILE_FOLDER = "static/profile_pics"
os.makedirs(PROFILE_FOLDER, exist_ok=True)


# =========================================================
# OCR EXPIRY DATE FUNCTION
# =========================================================

def extract_expiry_date(filepath):

    try:

        # IMAGE FILE
        if filepath.lower().endswith((".jpg", ".jpeg", ".png")):

            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)

        # PDF FILE
        elif filepath.lower().endswith(".pdf"):

            pages = convert_from_path(filepath)

            text = ""

            for page in pages:
                text += pytesseract.image_to_string(page)

        else:
            return None

        print("\n========== OCR TEXT ==========")
        print(text)
        print("==============================\n")

        text_lower = text.lower()

        # Date patterns
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
            r"\b\d{1,2}[.]\d{1,2}[.]\d{4}\b",
            r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
        ]

        # Expiry keywords
        expiry_keywords = [
            "expiry",
            "expires",
            "expiration",
            "valid till",
            "valid upto",
            "valid up to",
            "valid until",
            "validity",
            "expiry date",
            "date of expiry"
        ]

        # First search near expiry keyword
        for keyword in expiry_keywords:

            position = text_lower.find(keyword)

            if position != -1:

                nearby_text = text[
                    max(0, position - 50):
                    position + 150
                ]

                for pattern in date_patterns:

                    matches = re.findall(
                        pattern,
                        nearby_text
                    )

                    for match in matches:

                        clean_date = (
                            match
                            .replace(".", "/")
                            .replace("-", "/")
                        )

                        try:

                            parts = clean_date.split("/")

                            if len(parts[0]) == 4:

                                year = int(parts[0])
                                month = int(parts[1])
                                day = int(parts[2])

                            else:

                                day = int(parts[0])
                                month = int(parts[1])
                                year = int(parts[2])

                            expiry = date(
                                year,
                                month,
                                day
                            )

                            return expiry

                        except ValueError:
                            continue

        return None

    except Exception as e:

        print("OCR Error:", e)

        return None


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("home.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        sql = """
        SELECT *
        FROM users
        WHERE email=%s AND password=%s
        """

        cursor.execute(
            sql,
            (email, password)
        )

        user = cursor.fetchone()

        if user:

            session["user_id"] = user[0]
            session["user"] = user[1]

            return redirect("/dashboard")

        else:

            return render_template(
                "login.html",
                error="Invalid Email or Password"
            )

    return render_template("login.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]

        sql = """
        INSERT INTO users(fullname, email, password)
        VALUES(%s, %s, %s)
        """

        cursor.execute(
            sql,
            (fullname, email, password)
        )

        db.commit()

        return redirect("/login")

    return render_template("register.html")

# ===========================
# CITIZEN PROFILE
# ===========================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":

        fullname = request.form.get("fullname")
        dob = request.form.get("dob")
        gender = request.form.get("gender")
        mobile = request.form.get("mobile")
        education = request.form.get("education")
        occupation = request.form.get("occupation")
        marital_status = request.form.get("marital_status")
        income = request.form.get("income")
        state = request.form.get("state")
        district = request.form.get("district")

        # Upload Profile Photo
        photo = request.files.get("profile_photo")

        if photo and photo.filename != "":
            photo_name = secure_filename(photo.filename)
            photo.save(os.path.join(PROFILE_FOLDER, photo_name))

            cursor.execute("""
                UPDATE users
                SET profile_photo=%s
                WHERE id=%s
            """, (photo_name, user_id))

        # Update Profile Details
        cursor.execute("""
            UPDATE users
            SET fullname=%s,
                dob=%s,
                gender=%s,
                mobile=%s,
                education=%s,
                occupation=%s,
                marital_status=%s,
                income=%s,
                state=%s,
                district=%s
            WHERE id=%s
        """, (
            fullname,
            dob,
            gender,
            mobile,
            education,
            occupation,
            marital_status,
            income,
            state,
            district,
            user_id
        ))

        db.commit()
        return redirect("/profile")

    # Fetch user details
    cursor.execute("""
        SELECT fullname,dob,gender,mobile,
               education,occupation,marital_status,
               income,state,district,email,profile_photo
        FROM users
        WHERE id=%s
    """, (user_id,))

    data = cursor.fetchone()

    user = {
        "fullname": data[0],
        "dob": data[1],
        "gender": data[2],
        "mobile": data[3],
        "education": data[4],
        "occupation": data[5],
        "marital_status": data[6],
        "income": data[7],
        "state": data[8],
        "district": data[9],
        "email": data[10],
        "profile_photo": data[11]
    }

    return render_template("profile.html", user=user)


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # -----------------------------------------------------
    # TOTAL DOCUMENTS
    # -----------------------------------------------------
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=%s
    """, (user_id,))
    total_documents = cursor.fetchone()[0]

    # -----------------------------------------------------
    # GET ALL DOCUMENT EXPIRY DATES
    # -----------------------------------------------------
    cursor.execute("""
        SELECT expiry_date
        FROM documents
        WHERE user_id=%s
    """, (user_id,))
    all_documents = cursor.fetchall()

    today = date.today()
    valid_documents = 0
    expired_documents = 0

    # -----------------------------------------------------
    # CHECK DOCUMENT STATUS
    # -----------------------------------------------------
    for doc in all_documents:

        expiry = doc[0]

        if expiry:

            if isinstance(expiry, datetime):
                expiry = expiry.date()

            elif isinstance(expiry, str):
                try:
                    expiry = datetime.strptime(
                        expiry,
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    expiry = None

            if expiry:
                if expiry < today:
                    expired_documents += 1
                else:
                    valid_documents += 1

    # -----------------------------------------------------
    # GOVERNMENT SCHEMES COUNT
    # -----------------------------------------------------
    cursor.execute("""
        SELECT COUNT(DISTINCT scheme_name)
        FROM scheme_requirements
    """)
    eligible_schemes = cursor.fetchone()[0]

    # -----------------------------------------------------
    # GOVERNMENT READINESS SCORE
    # -----------------------------------------------------
    if total_documents == 0:
        readiness_score = 0
    else:
        readiness_score = round(
            (valid_documents / total_documents) * 100
        )

    # -----------------------------------------------------
    # DASHBOARD PAGE
    # -----------------------------------------------------
    return render_template(
        "dashboard.html",
        username=session["user"],
        total_documents=total_documents,
        valid_documents=valid_documents,
        expired_documents=expired_documents,
        eligible_schemes=eligible_schemes,
        readiness_score=readiness_score
    )


@app.route("/life-event")
def life_event():

    if "user" not in session:
        return redirect("/login")

    return render_template("life_event.html")

# =========================
# SCHOLARSHIP FINDER
# =========================
@app.route("/scholarship", methods=["GET", "POST"])
def scholarship():

    scholarships = []

    if request.method == "POST":

        course = request.form["course"]
        percentage = int(request.form["percentage"])
        income = int(request.form["income"])
        state = request.form["state"]

        # Eligible scholarships fetch pannum
        cursor.execute("""
            SELECT *
            FROM scholarships
            WHERE min_percentage <= %s
              AND max_income >= %s
              AND (state = %s OR state = 'All India')
        """, (percentage, income, state))

        data = cursor.fetchall()

        # AI Match Score calculate pannum
        for row in data:

            match_score = 100

            # Percentage bonus
            if percentage >= row[4] + 10:
                match_score = 98
            elif percentage >= row[4] + 5:
                match_score = 95
            elif percentage >= row[4]:
                match_score = 90

            scholarships.append({
                "name": row[1],
                "category": row[2],
                "state": row[3],
                "amount": row[6],
                "eligibility": row[7],
                "documents": row[8],
                "last_date": row[9],
                "apply_link": row[10],
                "match": match_score
            })

        # Highest match first
        scholarships.sort(key=lambda x: x["match"], reverse=True)

    return render_template(
        "scholarship.html",
        scholarships=scholarships
    )
@app.route("/education-loan")
def education_loan():
    return render_template("education_loan.html")
@app.route("/business-loan")
def business_loan():
    return render_template("business_loan.html")
@app.route("/startup-support")
def startup_support():
    return render_template("startup_support.html")
@app.route("/passport")
def passport():
    return render_template("passport.html")
@app.route("/driving-licence")
def driving_licence():
    return render_template("driving_licence.html")
@app.route("/housing")
def housing():
    return render_template("housing.html")
@app.route("/career")
def career():
    return render_template("career.html")
@app.route("/certificate")
def certificate():
    return render_template("certificate.html")
@app.route("/family-benefits")
def family_benefits():
    return render_template("family_benefits.html")

# =========================================================
# DOCUMENT UPLOAD
# =========================================================

@app.route("/document", methods=["GET", "POST"])
def document():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        user_id = session["user_id"]

        document_name = request.form["document_name"]

        file = request.files.get("document")

        if file and file.filename != "":

            filename = secure_filename(file.filename)

            filepath = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            file.save(filepath)

            # OCR expiry detection
            expiry_date = extract_expiry_date(filepath)

            print(
                "Detected Expiry Date:",
                expiry_date
            )

            # Save document
            sql = """
            INSERT INTO documents
            (user_id, document_name, file_name, expiry_date)
            VALUES(%s, %s, %s, %s)
            """

            cursor.execute(
                sql,
                (
                    user_id,
                    document_name,
                    filename,
                    expiry_date
                )
            )

            db.commit()

            # Status
            if expiry_date:

                today = date.today()

                if expiry_date < today:

                    status = "Expired"

                else:

                    status = "Valid"

                return f"""
                <h2>Document Uploaded Successfully</h2>

                <p>
                    Expiry Date:
                    {expiry_date.strftime("%d-%m-%Y")}
                </p>

                <p>
                    Status: {status}
                </p>

                <br>

                <a href="/mydocuments">
                    View My Documents
                </a>
                """

            else:

                return """
                <h2>Document Uploaded Successfully</h2>

                <p>
                    ⚠️ Expiry date could not be detected.
                </p>

                <br>

                <a href="/mydocuments">
                    View My Documents
                </a>
                """

    return render_template("document.html")


# =========================================================
# MY DOCUMENTS
# =========================================================

@app.route("/mydocuments")
def mydocuments():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor.execute(
        """
        SELECT *
        FROM documents
        WHERE user_id=%s
        """,
        (user_id,)
    )

    documents = cursor.fetchall()

    document_status = []

    today = date.today()

    for doc in documents:

        expiry_date = doc[4]

        if expiry_date:

            if isinstance(
                expiry_date,
                datetime
            ):

                expiry_date = expiry_date.date()

            elif isinstance(
                expiry_date,
                str
            ):

                try:

                    expiry_date = datetime.strptime(
                        expiry_date,
                        "%Y-%m-%d"
                    ).date()

                except ValueError:

                    expiry_date = None

        if expiry_date:

            if expiry_date < today:

                status = "Expired"

            else:

                status = "Valid"

        else:

            status = "Expiry Date Not Found"

        document_status.append(status)

    return render_template(
        "mydocuments.html",
        documents=documents,
        document_status=document_status
    )


# =========================================================
# DOCUMENT STATUS
# =========================================================

@app.route("/document-status")
def document_status():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    sql = """
    SELECT
        id,
        document_name,
        file_name,
        expiry_date
    FROM documents
    WHERE user_id=%s
    ORDER BY id DESC
    """

    cursor.execute(
        sql,
        (user_id,)
    )

    documents = cursor.fetchall()

    document_status_list = []

    today = date.today()

    for doc in documents:

        doc_id = doc[0]
        document_name = doc[1]
        file_name = doc[2]
        expiry_date = doc[3]

        status = "Expiry Date Not Found"

        if expiry_date:

            if isinstance(
                expiry_date,
                datetime
            ):

                expiry_date = expiry_date.date()

            elif isinstance(
                expiry_date,
                str
            ):

                try:

                    expiry_date = datetime.strptime(
                        expiry_date,
                        "%Y-%m-%d"
                    ).date()

                except ValueError:

                    expiry_date = None

        if expiry_date:

            if expiry_date < today:

                status = "Expired"

            elif expiry_date == today:

                status = "Expires Today"

            else:

                days_left = (
                    expiry_date - today
                ).days

                if days_left <= 30:

                    status = "Expiring Soon"

                else:

                    status = "Valid"

        document_status_list.append({

            "id": doc_id,

            "document_name": document_name,

            "file_name": file_name,

            "expiry_date": expiry_date,

            "status": status

        })

    return render_template(
        "document_status.html",
        documents=document_status_list
    )


# =========================================================
# VIEW DOCUMENT
# =========================================================

@app.route("/view/<filename>")
def view_document(filename):

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor.execute(
        """
        SELECT file_name
        FROM documents
        WHERE file_name=%s
        AND user_id=%s
        """,
        (filename, user_id)
    )

    file = cursor.fetchone()

    if not file:

        return "Access Denied", 403

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )


# =========================================================
# DOWNLOAD DOCUMENT
# =========================================================

@app.route("/download/<filename>")
def download_document(filename):

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor.execute(
        """
        SELECT file_name
        FROM documents
        WHERE file_name=%s
        AND user_id=%s
        """,
        (filename, user_id)
    )

    file = cursor.fetchone()

    if not file:

        return "Access Denied", 403

    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=True
    )


# =========================================================
# DELETE DOCUMENT
# =========================================================

@app.route("/delete/<int:id>")
def delete_document(id):

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor.execute(
        """
        SELECT file_name
        FROM documents
        WHERE id=%s
        AND user_id=%s
        """,
        (id, user_id)
    )

    file = cursor.fetchone()

    if file:

        filepath = os.path.join(
            UPLOAD_FOLDER,
            file[0]
        )

        if os.path.exists(filepath):

            os.remove(filepath)

        cursor.execute(
            """
            DELETE FROM documents
            WHERE id=%s
            AND user_id=%s
            """,
            (id, user_id)
        )

        db.commit()

    return redirect("/mydocuments")


# =========================================================
# HELP & SUPPORT
# =========================================================

@app.route("/complaint", methods=["GET", "POST"])
def complaint():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        fullname = request.form["fullname"]

        department = request.form["department"]

        complaint_text = request.form["complaint"]

        sql = """
        INSERT INTO complaints
        (fullname, department, complaint)
        VALUES(%s, %s, %s)
        """

        cursor.execute(
            sql,
            (
                fullname,
                department,
                complaint_text
            )
        )

        db.commit()

        return """
        <h2>
            Your support request has been
            submitted successfully.
        </h2>

        <br>

        <a href="/dashboard">
            Back to Dashboard
        </a>
        """

    return render_template("complaint.html")


# =========================================================
# AI CHATBOT
# =========================================================

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():

    answer = ""

    if request.method == "POST":

        question = request.form["question"].lower()

        if "aadhaar" in question:

            answer = (
                "You can apply for Aadhaar through "
                "the UIDAI official website."
            )

        elif "how to apply passport" in question:

            answer = (
                "You can apply for Passport through "
                "passportindia.gov.in."
            )

        elif "driving license" in question:

            answer = (
                "You can apply through the "
                "Parivahan Sewa portal."
            )

        elif "voter id" in question:

            answer = (
                "You can apply through the "
                "NVSP portal."
            )

        else:

            answer = (
                "Sorry, I don't have an answer "
                "for that yet."
            )

    return render_template(
        "chatbot.html",
        answer=answer
    )


# =========================================================
# GOVERNMENT SCHEMES
# =========================================================

@app.route("/schemes")
def schemes():

    if "user" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # User documents
    cursor.execute(
        """
        SELECT document_name, expiry_date
        FROM documents
        WHERE user_id=%s
        """,
        (user_id,)
    )

    user_docs = cursor.fetchall()

    # Scheme requirements
    cursor.execute(
        """
        SELECT scheme_name, required_document
        FROM scheme_requirements
        """
    )

    scheme_rows = cursor.fetchall()

    today = date.today()

    uploaded = {}
    expired = {}

    # Check uploaded documents
    for doc_name, expiry in user_docs:

        if expiry:

            if isinstance(
                expiry,
                datetime
            ):

                expiry = expiry.date()

            elif isinstance(
                expiry,
                str
            ):

                try:

                    expiry = datetime.strptime(
                        expiry,
                        "%Y-%m-%d"
                    ).date()

                except ValueError:

                    expiry = None

        uploaded[doc_name] = True

        if expiry and expiry < today:

            expired[doc_name] = True

    schemes_data = {}

    for scheme_name, required_doc in scheme_rows:

        if scheme_name not in schemes_data:

            schemes_data[scheme_name] = []

        if required_doc in uploaded:

            if required_doc in expired:

                status = "Expired"

            else:

                status = "Available"

        else:

            status = "Missing"

        schemes_data[scheme_name].append({

            "document": required_doc,

            "status": status

        })

    return render_template(
        "schemes.html",
        schemes=schemes_data
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop("user_id", None)
    session.pop("user", None)

    return redirect("/login")


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)