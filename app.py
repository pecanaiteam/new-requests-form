import os
import re
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

# inject the new ngrok URL into index.html
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
EXCEL_FILE = os.path.join(BASE_DIR, "submissions.xlsx")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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

@app.route("/", methods=["GET"])
def index():
    return send_from_directory(BASE_DIR, INDEX_PATH)

@app.route("/submit", methods=["POST"])
def submit():
    try:
        form = request.form
        files = request.files
        print("== Incoming submission ==")
        print("Form data:", form)
        print("Files:", files)

        row = [
            form.get("dealer_name", ""),
            form.get("email", ""),
            form.get("phone", ""),
            form.get("requestor_name", "")
        ]

        for i in range(1, 4):
            desc = form.get(f"feature_description_{i}", "")
            sev = form.get(f"severity_{i}", "")
            upload = files.get(f"attachment_{i}")
            print(f"Feature {i} -> Desc: {desc}, Severity: {sev}, File: {upload.filename if upload else 'None'}")

            fname = ""
            if upload and upload.filename:
                fname = secure_filename(upload.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                upload.save(filepath)
                print(f"Saved attachment to: {filepath}")
            row.extend([desc, sev, fname])

        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        ws.append(row)
        wb.save(EXCEL_FILE)
        print("Row saved to Excel:", row)
        return jsonify({"status": "success"})

    except Exception as e:
        print("Error during submission:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
