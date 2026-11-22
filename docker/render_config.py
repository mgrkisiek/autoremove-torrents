# Replace ${VAR} placeholders in the config with environment variables.
# Fails on a missing variable instead of silently leaving the placeholder in.
import os
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding='utf-8') as f:
    text = f.read()

missing = []

def substitute(match):
    name = match.group(1)
    if name not in os.environ:
        missing.append(name)
        return match.group(0)
    return os.environ[name]

text = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', substitute, text)
if missing:
    sys.exit('Missing environment variable(s) for %s: %s' % (src, ', '.join(sorted(set(missing)))))

fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as f:
    f.write(text)
