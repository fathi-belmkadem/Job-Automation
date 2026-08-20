from flask import Flask, request, send_file, jsonify, Response
import subprocess
import os
import uuid
import shutil

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"})

@app.route('/compile', methods=['POST'])
def compile_latex():
    data = request.json
    latex_code = data.get('latex_code')

    work_dir = f"/tmp/{uuid.uuid4()}"
    os.makedirs(work_dir)
    try:
        tex_file = os.path.join(work_dir, "document.tex")

        with open(tex_file, "w", encoding='utf-8') as f:
            f.write(latex_code)

        shutil.copy("/app/profile.jpg", os.path.join(work_dir, "profile.jpg"))

        cmd = ["xelatex", "-interaction=nonstopmode", "document.tex"]

        # Pass 1 — MUST NOT use check=True here.
        # TikZ remember picture/overlay leaves unresolved coordinates on pass 1,
        # which causes a non-zero exit code. check=True would throw an exception
        # and prevent pass 2 from ever running — so the blue header background
        # never gets drawn. We ignore the exit code on pass 1 intentionally.
        subprocess.run(cmd, cwd=work_dir, capture_output=True)

        # Pass 2 — coordinates are now resolved from the .aux file written by
        # pass 1. The header background rectangle renders correctly here.
        # We only check for errors on this final pass.
        result = subprocess.run(cmd, cwd=work_dir, capture_output=True)

        pdf_path = os.path.join(work_dir, "document.pdf")

        if not os.path.exists(pdf_path):
            # Return the last 3000 chars of the log for debugging
            log_path = os.path.join(work_dir, "document.log")
            log_content = ""
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                    log_content = lf.read()[-3000:]
            return {"error": "Compilation failed", "details": log_content}, 422

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return Response(pdf_bytes, mimetype='application/pdf')
    finally:
        # Work dirs live in /tmp inside the container — without this, a
        # long-running pod slowly fills its disk under sustained traffic.
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)