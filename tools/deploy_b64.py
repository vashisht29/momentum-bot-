import base64
import gzip
import os

cwd = os.path.dirname(os.path.abspath(__file__))
deploy_all_path = os.path.join(cwd, 'deploy_all.sh')
deploy_oneliner_path = os.path.join(cwd, 'deploy_oneliner.txt')

with open(deploy_all_path, 'rb') as f:
    data = f.read()

# Compress with gzip
compressed = gzip.compress(data)

# Base64 encode
b64_encoded = base64.b64encode(compressed).decode('utf-8')

# Format the command
command = f"pkill -f 'python.*main.py' 2>/dev/null; echo '{b64_encoded}' | base64 -d | gunzip > /root/momentum_bot/deploy_all.sh && bash /root/momentum_bot/deploy_all.sh\n"

with open(deploy_oneliner_path, 'w') as f:
    f.write(command)

print(f"Generated {deploy_oneliner_path} ({len(command)} chars)")
