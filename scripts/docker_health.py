#!/usr/bin/env python3
"""Docker servis durumunu ozetler (docker compose ps ciktisi olmadan)."""

import urllib.request

checks = [
    ('API :8000', 'http://127.0.0.1:8000/health'),
    ('Frontend :3000', 'http://127.0.0.1:3000/'),
]

print('=== Docker Saglik ===')
for name, url in checks:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            print(f'  [OK] {name} — HTTP {r.status}')
    except Exception as e:
        print(f'  [--] {name} — {e}')
