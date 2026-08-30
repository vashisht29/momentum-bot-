import base64
import os

cwd = os.path.dirname(os.path.abspath(__file__))

# Read trade_manager.py
with open(os.path.join(cwd, "trade_manager.py"), "r") as f:
    trade_manager_content = f.read()

# Read check_sl_tp.py
with open(os.path.join(cwd, "check_sl_tp.py"), "r") as f:
    check_sl_tp_content = f.read()

# Encode to base64
tm_b64 = base64.b64encode(trade_manager_content.encode("utf-8")).decode("utf-8")
c_b64 = base64.b64encode(check_sl_tp_content.encode("utf-8")).decode("utf-8")

# Generate deploy_vps.py contents
python_deploy_script = f"""# VPS Deployment Script in Python
import base64
import os
import subprocess

print("Stopping bot if running...")
subprocess.run("pkill -f 'python.*main.py'", shell=True)

print("Backing up active files...")
os.makedirs("backup/active_backup", exist_ok=True)
for f in ["trade_manager.py", "check_sl_tp.py"]:
    if os.path.exists(f):
        backup_path = f"backup/active_backup/{{f}}.bak"
        subprocess.run(f"cp {{f}} {{backup_path}}", shell=True)

print("Writing updated files...")
files = {{
    "trade_manager.py": "{tm_b64}",
    "check_sl_tp.py": "{c_b64}"
}}

for name, b64_data in files.items():
    with open(name, "wb") as f:
        f.write(base64.b64decode(b64_data))
    print(f"  [OK] {{name}} updated.")

print("\\n✅ DEPLOYMENT COMPLETE!")
print("Run the checker script to verify SL/TP:")
print("  python3 check_sl_tp.py")
print("Start the bot:")
print("  source venv/bin/activate && nohup python3 main.py > bot.log 2>&1 &")
"""

# Write deploy_vps.py
deploy_vps_path = os.path.join(cwd, "deploy_vps.py")
with open(deploy_vps_path, "w") as f:
    f.write(python_deploy_script)

print(f"Generated {deploy_vps_path}")
