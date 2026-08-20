import os

src_file = "src/apply_all.py"
with open(src_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_lines(start, end):
    return "".join(lines[start-1:end])

imports = "".join(lines[0:35])

os.makedirs("src/apply", exist_ok=True)
with open("src/apply/__init__.py", "w") as f: pass

# compiler.py
with open("src/apply/compiler.py", "w", encoding="utf-8") as f:
    f.write(imports + "\n")
    f.write(get_lines(389, 432))

# utils.py
with open("src/apply/utils.py", "w", encoding="utf-8") as f:
    f.write(imports + "\n")
    f.write(get_lines(36, 60))

# ai_agent.py
with open("src/apply/ai_agent.py", "w", encoding="utf-8") as f:
    f.write(imports + "\n")
    f.write("from .compiler import compile_cv\n\n")
    f.write(get_lines(63, 113) + "\n")
    f.write(get_lines(115, 297) + "\n")
    f.write(get_lines(302, 323) + "\n")
    f.write(get_lines(325, 386) + "\n")
    f.write(get_lines(435, 503) + "\n")

# browser.py
with open("src/apply/browser.py", "w", encoding="utf-8") as f:
    f.write(imports + "\n")
    f.write("from .ai_agent import find_element_with_ai, answer_questions\n\n")
    f.write(get_lines(506, 820) + "\n")

# main entrypoint
with open("src/apply_all.py", "w", encoding="utf-8") as f:
    f.write(imports + "\n")
    f.write("from apply.utils import get_cv_template\n")
    f.write("from apply.compiler import compile_cv\n")
    f.write("from apply.ai_agent import tailor_cv, tailor_cover_letter\n")
    f.write("from apply.browser import apply_to_job\n\n")
    f.write(get_lines(823, 907))

print("Refactoring complete.")
