import os
import sys
from pathlib import Path
import requests

sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings


def compile_pdf(tex_content, output_dir, filename_base):
    # Save .tex
    tex_file = os.path.join(output_dir, f"{filename_base}.tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_content)

    print(f"   [Compile] Compiling {filename_base}.tex...")

    pdf_path = os.path.join(output_dir, f"{filename_base}.pdf")

    try:
        response = requests.post(
            f"{settings.LATEX_COMPILER_URL}/compile",
            json={"latex_code": tex_content},
            timeout=120,
        )

        if response.status_code == 200:
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            return pdf_path
        else:
            print(f"   [Error] PDF compilation failed (HTTP {response.status_code}).")
            error_text = response.text or ""
            if "!" in error_text:
                idx = error_text.find("!")
                error_snippet = error_text[idx: idx + 150]
                print(f"   [LaTeX Error] Detected: {error_snippet.strip()}")

            # Save logs for debugging
            log_path = os.path.join("debug", f"{filename_base}_compile_error.log")
            os.makedirs("debug", exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"HTTP STATUS: {response.status_code}\n\nRESPONSE:\n{error_text}")
            print(f"   [Debug] Full compiler response saved to {log_path}")
            return None
    except Exception as e:
        print(f"   [Error] LaTeX compiler request failed with Exception: {e}")
        return None
