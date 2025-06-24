from flask import Flask, request, jsonify
from flask_cors import CORS
from openpyxl import Workbook, load_workbook
from werkzeug.utils import secure_filename
from github import Github, GithubException
import os

# push this file to your GitHub repo on each run
token = os.getenv("GITHUB_TOKEN")
repo_name = os.getenv("GITHUB_REPO")
if token and repo_name:
    gh = Github(token)
    try:
        repo = gh.get_repo(repo_name)
        path = os.path.basename(__file__)
        with open(__file__, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            contents = repo.get_contents(path, ref="main")
            repo.update_file(
                contents.path,
                "update app.py",
                code,
                contents.sha,
                branch="main"
            )
            print("updated app.py on github")
        except GithubException:
            repo.create_file(
                path,
                "add app.py",
                code,
                branch="main"
            )
            print("created app.py on github")
    except Exception as e:
        print("github push error:", e)
else:
    print("set GITHUB_TOKEN and GITHUB_REPO env vars to enable github push")

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, 'submissions.xlsx')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create Excel file with headers if not exists
if not os.path.exists(EXCEL_FILE):
    wb = Workbook()
    ws = wb.active
    ws.append([
        "Dealer Name", "Email", "Phone", "Requestor Name",
        "Feature 1 Description", "Feature 1 Severity", "Feature 1 Attachment",
        "Feature 2 Description", "Feature 2 Severity", "Feature 2 Attachment",
        "Feature 3 Description", "Feature 3 Severity", "Feature 3 Attachment"
    ])
    wb.save(EXCEL_FILE)

@app.route("/submit", methods=["POST"])
def submit():
    try:
        form = request.form
        files = request.files
        dealer = form.get("dealer_name", "")
        email = form.get("email", "")
        phone = form.get("phone", "")
        requestor = form.get("requestor_name", "")
        row = [dealer, email, phone, requestor]

        for i in range(1, 4):
            desc = form.get(f"feature_description_{i}", "")
            severity = form.get(f"severity_{i}", "")
            file = files.get(f"attachment_{i}")
            filename = ""
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
            row.extend([desc, severity, filename])

        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        ws.append(row)
        wb.save(EXCEL_FILE)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000)
