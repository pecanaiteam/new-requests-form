import os
import re
from datetime import datetime
from pyngrok import ngrok
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openpyxl import Workbook, load_workbook
from werkzeug.utils import secure_filename
from github import Github, GithubException

# start an http‐only ngrok tunnel on port 5000
ngrok.kill()
tunnel = ngrok.connect(5000, proto="http", bind_tls=False)
public_url = tunnel.public_url
print("ngrok public url:", public_url)

# inject the new ngrok URL into index.html (so form.action updates)
INDEX_PATH = "index.html"
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()
new_action = f'action="{public_url}/submit"'
updated_html = re.sub(r'action="https?://[^"]+/submit"', new_action, html)
if updated_html != html:
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(updated_html)
    print("index.html updated with new ngrok URL")

# push index.html and this file to GitHub
token = os.getenv("GITHUB_TOKEN")
repo_name = os.getenv("GITHUB_REPO")
if token and repo_name:
    gh = Github(token)
    try:
        repo = gh.get_repo(repo_name)
        for fname in (INDEX_PATH, os.path.basename(__file__)):
            with open(fname, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                contents = repo.get_contents(fname, ref="main")
                repo.update_file(
                    contents.path,
                    f"Auto-update {fname}",
                    content,
                    contents.sha,
                    branch="main"
                )
                print(f"updated {fname} on github")
            except GithubException:
                repo.create_file(
                    fname,
                    f"Add {fname}",
                    content,
                    branch="main"
                )
                print(f"created {fname} on github")
    except Exception as e:
        print("github push error:", e)
else:
    print("set GITHUB_TOKEN and GITHUB_REPO env vars to enable github push")

# flask and excel setup
app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# point at the seeded file or flat file as you prefer:
# EXCEL_FILE = os.path.join(BASE_DIR, "submissions", "submissions.xlsx")
EXCEL_FILE = os.path.join(BASE_DIR, "submissions.xlsx")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# create workbook with new headers if missing
if not os.path.exists(EXCEL_FILE):
    wb = Workbook()
    ws = wb.active
    ws.append([
        "Timestamp",
        "Requestor Name",
        "Dealer Name",
        "Email",
        "Phone",
        "Feature 1 Name",
        "Feature 1 Priority",
        "Feature 1 Description",
        "Feature 1 Severity",
        "Feature 1 Attachment",
        "Feature 2 Name",
        "Feature 2 Priority",
        "Feature 2 Description",
        "Feature 2 Severity",
        "Feature 2 Attachment",
        "Feature 3 Name",
        "Feature 3 Priority",
        "Feature 3 Description",
        "Feature 3 Severity",
        "Feature 3 Attachment"
    ])
    wb.save(EXCEL_FILE)
    print(f"Initialized Excel at {EXCEL_FILE}")

@app.route("/", methods=["GET"])
def index():
    return send_from_directory(BASE_DIR, INDEX_PATH)

@app.route("/submit", methods=["POST"])
def submit():
    try:
        form = request.form
        files = request.files

        # build row in header order
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            form.get("requestor_name", ""),
            form.get("dealer_name", ""),
            form.get("email", ""),
            form.get("phone", "")
        ]

        # for each feature slot
        for i in range(1, 4):
            # new fields feature_name and priority
            name = form.get(f"feature_name_{i}", "")
            priority = form.get(f"priority_{i}", "")
            desc = form.get(f"feature_description_{i}", "")
            sev = form.get(f"severity_{i}", "")
            upload = files.get(f"attachment_{i}")
            fname = ""
            if upload and upload.filename:
                fname = secure_filename(upload.filename)
                upload.save(os.path.join(UPLOAD_FOLDER, fname))
            row.extend([name, priority, desc, sev, fname])

        # append to Excel
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        ws.append(row)
        wb.save(EXCEL_FILE)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
