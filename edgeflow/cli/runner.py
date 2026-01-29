# edgeflow/cli/runner.py
import subprocess
import sys
import shutil
from pathlib import Path

def run_local(file_path: str = "main.py"):
    """
    Run the EdgeFlow application locally using 'uv run'.
    This ensures that the application runs in the project's virtual environment
    with all dependencies (node.toml) available.
    """
    target_file = Path(file_path)
    if not target_file.exists():
        print(f"❌ Error: File '{file_path}' not found.")
        return

    # 1. Check for uv
    if not shutil.which("uv"):
        print("❌ Error: 'uv' is not installed. Please install it first.")
        print("  Full Guide: https://github.com/astral-sh/uv")
        return

    # 2. Construct Command: uv run python {file}
    # - This automatically sets up the venv if needed and runs the script
    cmd = ["uv", "run", "python", str(target_file)]
    
    print(f"🚀 [EdgeFlow Local] Running: {' '.join(cmd)}")
    print(f"   (Press Ctrl+C to stop)")
    print("-" * 50)

    try:
        # Use simple subprocess to inherit IO
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Stopped.")
    except Exception as e:
        print(f"❌ Error running local: {e}")
