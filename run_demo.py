"""Run demo and capture output."""
import subprocess, sys
r = subprocess.run(
    [sys.executable, "scripts/demo_full_pipeline.py"],
    capture_output=True, text=True, cwd=r"c:\VS Code Folders\Echo-Mind"
)
with open("demo_output.txt", "w", encoding="utf-8") as f:
    f.write(r.stdout)
    if r.stderr:
        f.write("\n--- STDERR ---\n")
        f.write(r.stderr)
print(r.stdout)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
