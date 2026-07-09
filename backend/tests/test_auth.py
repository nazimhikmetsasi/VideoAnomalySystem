import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.auth import authenticate_user, create_access_token, hash_password, verify_password, _jwt_decode


def test_hash_and_verify():
    h = hash_password('test123')
    assert verify_password('test123', h)
    assert not verify_password('wrong', h)


def test_authenticate_default_admin():
    user = authenticate_user('admin', 'admin123')
    assert user is not None
    assert user['role'] == 'admin'


def test_jwt_roundtrip():
    token = create_access_token({'username': 'admin', 'role': 'admin'})
    payload = _jwt_decode(token)
    assert payload['sub'] == 'admin'
    assert payload['role'] == 'admin'
