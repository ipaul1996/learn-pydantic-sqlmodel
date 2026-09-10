from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel

# Security — OAuth2 password flow + JWT tokens
# Builds on fastapi6-7.py (Depends). This is the real, usable pattern: hashed
# passwords at rest, a signed JWT as the access token, and a dependency chain
# that turns "Authorization: Bearer <token>" into a validated current user.
#
# pip packages used here: pyjwt (JWT encode/decode), pwdlib[argon2] (hashing).

# In real code, generate this with: openssl rand -hex 32 — and load it from an
# environment variable / secrets manager (see sqlmodel9.py for pydantic-settings).
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


# Password hashing — never store or compare plaintext passwords. pwdlib's
# recommended algorithm is Argon2 (the winner of the Password Hashing Competition).
password_hash = PasswordHash.recommended()

# A precomputed dummy hash — verified against on a "user not found" path so that
# a login attempt for a real vs. a fake username takes roughly the same amount of
# time either way. Without this, timing differences let an attacker enumerate
# valid usernames just by measuring response latency.
DUMMY_HASH = password_hash.hash("dummypassword")

fake_users_db: dict[str, dict] = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": password_hash.hash("secret"),
        "disabled": False,
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_user(db: dict[str, dict], username: str) -> UserInDB | None:
    if username in db:
        return UserInDB(**db[username])
    return None


def authenticate_user(fake_db: dict[str, dict], username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, DUMMY_HASH)  # burn the same time as a real check
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# OAuth2PasswordBearer — reads the "Authorization: Bearer <token>" header, returns
# the raw token string. tokenUrl="token" only tells the DOCS where to send the
# login form from the "Authorize" button; it does NOT create that endpoint itself.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="OAuth2 + JWT")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception

    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# The login endpoint — OAuth2PasswordRequestForm reads username/password (and an
# optional scope/grant_type/client_id) from FORM DATA, per the OAuth2 spec (not JSON).
@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me/")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("POST /token — wrong password -> 401")
    r = client.post("/token", data={"username": "johndoe", "password": "wrong"})
    print(r.status_code, r.json())

    print("\nPOST /token — unknown user -> same 401, same rough latency (timing-safe)")
    r = client.post("/token", data={"username": "nobody", "password": "whatever"})
    print(r.status_code, r.json())

    print("\nGET /users/me/ with no token -> 401")
    r = client.get("/users/me/")
    print(r.status_code, r.json())

    print("\nPOST /token — correct credentials -> real JWT access token")
    r = client.post("/token", data={"username": "johndoe", "password": "secret"})
    token = r.json()["access_token"]
    print(r.status_code, r.json())

    print("\nGET /users/me/ with a valid Bearer token")
    r = client.get("/users/me/", headers={"Authorization": f"Bearer {token}"})
    print(r.status_code, r.json())

    print("\nGET /users/me/ with a tampered token -> 401")
    r = client.get("/users/me/", headers={"Authorization": "Bearer not-a-real-token"})
    print(r.status_code, r.json())

    print("\nDecoding the token payload directly (for illustration only)")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    print(payload)  # {'sub': 'johndoe', 'exp': ...}


# Summary
#
# PasswordHash.recommended()          -> Argon2 hashing; .hash(pw) / .verify(pw, hash)
# DUMMY_HASH + verify on missing user -> mitigates username-enumeration via timing attacks
# OAuth2PasswordBearer(tokenUrl=...)  -> reads "Authorization: Bearer <token>", used with Depends
# OAuth2PasswordRequestForm           -> reads username/password as FORM data (OAuth2 spec)
# jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM) -> sign a token; "exp" claim = expiry
# jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) -> verify + read it back; raises
#                                         InvalidTokenError on tampering/expiry
# "sub" claim                          -> the token's subject, typically the username/user id
# get_current_user -> get_current_active_user  -> layered dependencies: "who is this" then
#                                         "are they allowed to act" (disabled check)
#
# Continue in fastapi11.py for file uploads, forms, custom responses, and WebSockets.
