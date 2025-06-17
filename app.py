from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openpyxl import Workbook, load_workbook
from werkzeug.utils import secure_filename
from pyngrok import ngrok
from github import Github, GithubException
import os

app = Flask(__name__)
CORS(app)

# start ngrok on port 5000
public_url = ngrok.connect(5000).public_url
print("ngrok public url:", public_url)

# push app.py and index.html to your github repo
token = os.getenv("GITHUB_TOKEN")
repo_name = os.getenv("GITHUB_REPO")
if token and repo_name:
    gh = Github(token)
    try:
        repo = gh.get_repo(repo_name)
        for fname in ["app.py", "index.html"]:
            with open(fname, "r") as f:
                content = f.read()
            try:
                contents = repo.get_contents(fname, ref="main")
                repo.update_file(
                    contents.path,
                    f"update {fname}",
                    content,
                    contents.sha,
                    branch="main"
                )
                print(f"updated {fname} on github")
            except GithubException:
                repo.create_file(
                    fname,
                    f"add {fname}",
                    content,
                    branch="main"
                )
                print(f"created {fname} on github")
    except Exception as e:
        print("github push error:", e)
else:
    print("set GITHUB_TOKEN and GITHUB_REPO env vars to enable github push")

# excel and upload setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "submissions.xlsx")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# init excel if missing
if not os.path.exists(EXCEL_FILE):
    wb = Workbook()
    ws = wb.active
    ws.append([
        "Dealer Name","Email","Phone","Requestor Name",
        "Feature 1 Description","Feature 1 Severity","Feature 1 Attachment",
        "Feature 2 Description","Feature 2 Severity","Feature 2 Attachment",
        "Feature 3 Description","Feature 3 Severity","Feature 3 Attachment"
    ])
    wb.save(EXCEL_FILE)

# serve your form
@app.route("/", methods=["GET"])
def index():
    return send_from_directory(BASE_DIR, "index.html")

# handle form submit
@app.route("/submit", methods=["POST"])
def submit():
    try:
        form = request.form
        files = request.files
        row = [
            form.get("dealer_name",""),
            form.get("email",""),
            form.get("phone",""),
            form.get("requestor_name","")
        ]
        for i in range(1,4):
            desc = form.get(f"feature_description_{i}","")
            sev  = form.get(f"severity_{i}","")
            upload = files.get(f"attachment_{i}")
            fname = ""
            if upload and upload.filename:
                fname = secure_filename(upload.filename)
                upload.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            row.extend([desc, sev, fname])
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        ws.append(row)
        wb.save(EXCEL_FILE)
        return jsonify({"status":"success"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}),500

if __name__ == "__main__":
    app.run(port=5000)
