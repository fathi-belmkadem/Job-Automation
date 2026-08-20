import pandas as pd
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import os
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

app = Flask(__name__, template_folder='../templates')
CORS(app)

DB_PATH = settings.JOBS_DB_PATH

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"})

@app.route('/api/jobs')
def get_jobs():
    if not os.path.exists(DB_PATH):
        return jsonify([])
    
    try:
        df = pd.read_excel(DB_PATH)
        df = df.fillna('')
        df['_index'] = df.index
        jobs = df.to_dict('records')
        return jsonify(jobs)
    except Exception as e:
        print(f"Error reading DB: {e}")
        return jsonify([])

# --- PDF VIEWER API ---
import glob
from flask import send_file

@app.route('/api/pdf/<int:job_id>/<doc_type>')
def get_pdf(job_id, doc_type):
    apps_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "My_Applications")
    pattern = os.path.join(apps_dir, f"{job_id}_*")
    folders = glob.glob(pattern)
    
    if not folders:
        return "Not found", 404
        
    target_dir = folders[0]
    
    if doc_type == 'cv':
        pdf_path = os.path.join(target_dir, "Fathi-BELMKADEM-CV.pdf")
    else:
        pdf_path = os.path.join(target_dir, "Fathi-BELMKADEM-CoverLetter.pdf")
        
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype='application/pdf')
    else:
        return "PDF not generated yet", 404

# --- ACTIONS & STATUS API ---
import subprocess
from flask import request

current_process = None
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "dashboard_run.log")

@app.route('/api/action/<action_name>', methods=['POST'])
def trigger_action(action_name):
    global current_process
    
    if current_process and current_process.poll() is None:
        return jsonify({"status": "error", "message": "A pipeline task is already running."}), 400

    cmd = [sys.executable, "main_pipeline.py"]
    
    if action_name == "harvest": cmd.extend(["-s", "1"])
    elif action_name == "filter": cmd.extend(["-s", "2"])
    elif action_name == "enrich": cmd.extend(["-s", "3"])
    elif action_name == "classify": cmd.extend(["-s", "4"])
    elif action_name == "apply": cmd.extend(["-s", "5"])
    elif action_name == "full": pass
    else: return jsonify({"status": "error", "message": "Unknown action"}), 400

    try:
        # Clear log file and start new run
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"--- Starting Task: {action_name.upper()} ---\n")
            
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
            
        log_f = open(LOG_FILE, "a", encoding="utf-8")
        current_process = subprocess.Popen(
            cmd, 
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=log_f,
            stderr=log_f,
            env=env
        )
        return jsonify({"status": "success", "message": f"Started task: {action_name.upper()}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status')
def get_status():
    global current_process
    is_running = current_process is not None and current_process.poll() is None
    return jsonify({"is_running": is_running})

@app.route('/api/logs')
def get_logs():
    if not os.path.exists(LOG_FILE): return jsonify({"logs": ""})
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f: return jsonify({"logs": f.read()})
    except: return jsonify({"logs": "Error reading logs."})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    keywords_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "keywords.json")
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "prompts", "prompt.txt")
    personal_info_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "personal_info.txt")
    import json
    
    if request.method == 'GET':
        try:
            with open(keywords_path, "r", encoding="utf-8") as f: keywords = json.load(f)
            with open(prompt_path, "r", encoding="utf-8") as f: prompt_txt = f.read()
            with open(personal_info_path, "r", encoding="utf-8") as f: personal_txt = f.read()
            return jsonify({"keywords": keywords, "prompt": prompt_txt, "personal_info": personal_txt})
        except: return jsonify({"keywords": [], "prompt": "", "personal_info": ""})
    else:
        data = request.json
        try:
            if "keywords" in data:
                with open(keywords_path, "w", encoding="utf-8") as f: json.dump(data["keywords"], f, indent=4)
            if "prompt" in data:
                with open(prompt_path, "w", encoding="utf-8") as f: f.write(data["prompt"])
            if "personal_info" in data:
                with open(personal_info_path, "w", encoding="utf-8") as f: f.write(data["personal_info"])
            return jsonify({"status": "success"})
        except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("   XING AUTOMATION DASHBOARD")
    print("   Running at: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
