import os

cwd = os.path.dirname(os.path.abspath(__file__))
files = {}
for fn in ['config.py', 'confirmation.py', 'trade_manager.py', 'strategy.py', 'main.py', 'check_sl_tp.py', 'check_rejections.py']:
    with open(os.path.join(cwd, fn)) as f:
        files[fn] = f.read()

tags = {}
for fn in files:
    tag = 'ENDOF_' + fn.replace('.', '_').upper()
    tags[fn] = tag
    if tag in files[fn]:
        print(f"DANGER: {fn} contains '{tag}'!")
    else:
        print(f"SAFE: {fn}")

out = []
out.append('#!/bin/bash')
out.append('set -e')
out.append('cd /root/momentum_bot')
out.append('pkill -f "python.*main.py" 2>/dev/null || true')
out.append('sleep 1')
out.append('mkdir -p backup/active_backup')
out.append('for f in config.py confirmation.py trade_manager.py strategy.py main.py check_sl_tp.py check_rejections.py; do')
out.append('  [ -f "$f" ] && cp "$f" "backup/active_backup/${f}.bak" || true')
out.append('done')
out.append('')

for fn in ['config.py', 'confirmation.py', 'trade_manager.py', 'strategy.py', 'main.py', 'check_sl_tp.py', 'check_rejections.py']:
    tag = tags[fn]
    out.append(f"cat > {fn} << '{tag}'")
    out.append(files[fn].rstrip())
    out.append(tag)
    out.append(f'echo "[OK] {fn}"')
    out.append('')

out.append('echo "ALL DONE"')
out.append('echo "Run: source venv/bin/activate && nohup python3 main.py > bot.log 2>&1 &"')

with open(os.path.join(cwd, 'deploy_all.sh'), 'w') as f:
    f.write('\n'.join(out) + '\n')

size = os.path.getsize(os.path.join(cwd, 'deploy_all.sh'))
print(f"Wrote deploy_all.sh: {size} bytes")
