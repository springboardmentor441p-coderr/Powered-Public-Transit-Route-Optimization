"""
RouteRanker Authentication & Role-Based Access Control (RBAC).
Provides zero-dependency JWT token generation/validation (HMAC-SHA256)
and password hashing for Admin, Operator, and Viewer roles.
"""
import hmac
import hashlib
import base64
import json
import time
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "routeranker-super-secret-jwt-key-2026"
ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours

# Preconfigured Users (Password hashing: sha256 with static salt for demo stability)
USERS_DB = {
    "admin": {
        "username": "admin",
        "name": "System Administrator",
        "role": "admin",
        "password_hash": hashlib.sha256("admin123-salt-2026".encode()).hexdigest(),
        "permissions": ["all", "manage_schedules", "broadcast_alerts", "view_analytics"],
    },
    "operator": {
        "username": "operator",
        "name": "Transit Operations Lead",
        "role": "operator",
        "password_hash": hashlib.sha256("operator123-salt-2026".encode()).hexdigest(),
        "permissions": ["manage_schedules", "broadcast_alerts", "view_analytics"],
    },
    "viewer": {
        "username": "viewer",
        "name": "Public Transit Analyst",
        "role": "viewer",
        "password_hash": hashlib.sha256("viewer123-salt-2026".encode()).hexdigest(),
        "permissions": ["view_analytics"],
    },
}

security_scheme = HTTPBearer(auto_error=False)

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if (len(data) % 4) != 0 else ''
    return base64.urlsafe_b64decode(data + padding)

def create_jwt_token(payload: dict) -> str:
    """Generate a standard HMAC-SHA256 JWT token."""
    header = {"alg": ALGORITHM, "typ": "JWT"}
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + TOKEN_EXPIRY_SECONDS
    payload_copy["iat"] = int(time.time())
    
    header_b64 = _base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(payload_copy).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    
    signature = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_jwt_token(token: str) -> dict:
    """Verify and decode a standard HMAC-SHA256 JWT token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
        actual_sig = _base64url_decode(sig_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Invalid token signature")
        
        payload = json.loads(_base64url_decode(payload_b64).decode('utf-8'))
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token has expired")
        
        return payload
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Verify credentials and return user record if valid."""
    user = USERS_DB.get(username)
    if not user:
        return None
    test_hash = hashlib.sha256(f"{password}-salt-2026".encode()).hexdigest()
    if hmac.compare_digest(user["password_hash"], test_hash):
        return {
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "permissions": user["permissions"],
        }
    return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)) -> Optional[dict]:
    """Extract authenticated user from Authorization: Bearer <token> header, or None if guest."""
    if not credentials:
        return None
    token = credentials.credentials
    return verify_jwt_token(token)

def require_authenticated_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    return user

def require_operator_or_admin(user: dict = Depends(require_authenticated_user)) -> dict:
    if user.get("role") not in ["admin", "operator"]:
        raise HTTPException(status_code=403, detail="Forbidden: Operator or Admin role required.")
    return user
