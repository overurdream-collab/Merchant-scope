import pytest
from app.pg_identity import hash_password,verify_password,token_hash

def test_hash_and_verify():
    h=hash_password("twelve characters secret")
    assert "twelve characters secret" not in h
    assert verify_password("twelve characters secret",h)
    assert not verify_password("incorrect password",h)
    assert hash_password("twelve characters secret") != h

def test_password_policy():
    with pytest.raises(ValueError): hash_password("short")
    assert not verify_password("abc","not-valid")

def test_token_is_sha256():
    token="secret-bearer-token"
    assert len(token_hash(token))==32
    assert token.encode() not in token_hash(token)
