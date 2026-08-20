import pandas as pd
from flask import Flask, jsonify, render_template, send_file, request
from flask_cors import CORS
import os
import sys
import subprocess
import glob
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))
from config import settings

app = Flask(__name__, template_folder='../templates')
CORS(app)

DB_PATH = settings.FILTERED_JOBS_FILE
LOG_FILE = PROJECT_ROOT / "output" / "dashboard_run.log"
current_process = None

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"})

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/meta.json')
def meta_json():
    return jsonify({"status": "ok"})

@app.route('/api/jobs')
def get_jobs():
    if not os.path.exists(DB_PATH):
        return jsonify([])
    try:
        # Use a temporary copy if needed, or just read
        # For Excel files, reading while writing can be tricky
        df = pd.read_excel(DB_PATH, engine='openpyxl')
        df = df.fillna('')
        df['_index'] = df.index
        return jsonify(df.to_dict('records'))
    except Exception as e:
        print(f"   [Dashboard Error] Failed to read {DB_PATH}: {e}")
        return jsonify({"error": "Database is currently busy or unavailable."})

@app.route('/api/pdf/<int:job_id>/<doc_type>')
def get_pdf(job_id, doc_type):
    # Find the job folder in output/My_Applications
    apps_dir = PROJECT_ROOT / "output" / "My_Applications"
    if not apps_dir.exists():
        return "Applications directory not found", 404
        
    # Get job info to find folder
    df = pd.read_excel(DB_PATH)
    job = df.iloc[job_id]
    company = str(job.get('Company', 'Unknown')).replace(' ', '_')
    title = str(job.get('Title', 'Unknown')).replace(' ', '_')
    
    # Search for folder matching pattern
    pattern = str(apps_dir / f"*_{company}_{job_id}")
    folders = glob.glob(pattern)
    
    if not folders:
        return f"Folder not found for job {job_id}", 404
        
    target_dir = Path(folders[0])
    
    filename = "CV.pdf" if doc_type == 'cv' else "CoverLetter.pdf"
    # Find any pdf in the folder if the exact name differs
    pdf_files = list(target_dir.glob("*.pdf"))
    
    if doc_type == 'cv':
        target_file = next((f for f in pdf_files if "CV" in f.name), None)
    else:
        target_file = next((f for f in pdf_files if "CoverLetter" in f.name or "Cover_Letter" in f.name), None)

    if target_file and target_file.exists():
        return send_file(str(target_file), mimetype='application/pdf')
    return "PDF not found", 404

@app.route('/api/action/<action_name>', methods=['POST'])
def trigger_action(action_name):
    global current_process
    if current_process and current_process.poll() is None:
        return jsonify({"status": "error", "message": "Pipeline already running"}), 400

    cmd = [sys.executable, str(PROJECT_ROOT / "src" / "main_pipeline.py")]
    
    if action_name == "fetch": cmd.append("--fetch")
    elif action_name == "filter": cmd.append("--filter") # Note: main_pipeline --filter runs all 3 filter steps
    elif action_name == "enrich": cmd = [sys.executable, str(PROJECT_ROOT / "src" / "enrich_jobs.py")]
    elif action_name == "filter_deep": cmd = [sys.executable, str(PROJECT_ROOT / "src" / "filter_deep.py")]
    elif action_name == "apply": cmd.append("--apply")
    elif action_name == "all": cmd.append("--all")
    else: return jsonify({"status": "error", "message": "Invalid action"}), 400

    os.makedirs(LOG_FILE.parent, exist_ok=True)
    log_f = open(LOG_FILE, "w", encoding="utf-8")
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    current_process = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=log_f, stderr=log_f, env=env)
    return jsonify({"status": "success", "message": f"Started {action_name}"})

@app.route('/api/status')
def get_status():
    is_running = current_process is not None and current_process.poll() is None
    return jsonify({"is_running": is_running})

@app.route('/api/logs')
def get_logs():
    if not LOG_FILE.exists(): return jsonify({"logs": ""})
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return jsonify({"logs": f.read()})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        return jsonify({
            "personal_info": open(settings.PERSONAL_INFO_FILE, "r").read() if os.path.exists(settings.PERSONAL_INFO_FILE) else "",
            "prompt": open(settings.SMART_QUESTIONS_PROMPT_FILE, "r").read() if os.path.exists(settings.SMART_QUESTIONS_PROMPT_FILE) else ""
        })
    else:
        data = request.json
        if "personal_info" in data:
            with open(settings.PERSONAL_INFO_FILE, "w") as f: f.write(data["personal_info"])
        if "prompt" in data:
            with open(settings.SMART_QUESTIONS_PROMPT_FILE, "w") as f: f.write(data["prompt"])
        return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
