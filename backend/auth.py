import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Dict, List, Optional

from backend.database import get_connection, initialize_database, log_audit

PBKDF2_ITERATIONS = 120_000

MANGALORE_BRANCHES: List[Dict[str, object]] = [
    {"branch_code": "HK", "branch_name": "Hampankatta", "storage_capacity": 6000},
    {"branch_code": "KD", "branch_name": "Kadri", "storage_capacity": 5500},
    {"branch_code": "BJ", "branch_name": "Bejai", "storage_capacity": 5000},
    {"branch_code": "KK", "branch_name": "Kankanady", "storage_capacity": 5000},
    {"branch_code": "UR", "branch_name": "Urwa", "storage_capacity": 4500},
]

# Clearly marked demonstration credentials for project evaluation
DEMO_CREDENTIALS: List[Dict[str, Optional[str]]] = [
    {
        "username": "admin",
        "password": "Admin@123",
        "full_name": "Main Store Admin",
        "role": "admin",
        "branch_code": None,
    },
    {
        "username": "hk_manager",
        "password": "Branch@123",
        "full_name": "Hampankatta Branch Manager",
        "role": "manager",
        "branch_code": "HK",
    },
    {
        "username": "kd_manager",
        "password": "Branch@123",
        "full_name": "Kadri Branch Manager",
        "role": "manager",
        "branch_code": "KD",
    },
    {
        "username": "bj_manager",
        "password": "Branch@123",
        "full_name": "Bejai Branch Manager",
        "role": "manager",
        "branch_code": "BJ",
    },
    {
        "username": "kk_manager",
        "password": "Branch@123",
        "full_name": "Kankanady Branch Manager",
        "role": "manager",
        "branch_code": "KK",
    },
    {
        "username": "ur_manager",
        "password": "Branch@123",
        "full_name": "Urwa Branch Manager",
        "role": "manager",
        "branch_code": "UR",
    },
]


def hash_password(password: str) -> str:
    """Hash a plain password using PBKDF2-HMAC-SHA256 with a random salt."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored PBKDF2 hash safely."""
    try:
        algorithm, salt_hex, hash_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def seed_branches_and_demo_users(db_path: Optional[Path] = None) -> None:
    """Insert the 5 Mangalore branches and demo accounts if missing."""
    initialize_database(db_path)

    with get_connection(db_path) as conn:
        for branch in MANGALORE_BRANCHES:
            conn.execute(
                """
                INSERT OR IGNORE INTO branches (
                    branch_code, branch_name, storage_capacity
                )
                VALUES (?, ?, ?);
                """,
                (
                    branch["branch_code"],
                    branch["branch_name"],
                    branch["storage_capacity"],
                ),
            )

        for account in DEMO_CREDENTIALS:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?;",
                (account["username"],),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, full_name,
                        role, branch_code, is_demo
                    )
                    VALUES (?, ?, ?, ?, ?, 1);
                    """,
                    (
                        account["username"],
                        hash_password(account["password"]),
                        account["full_name"],
                        account["role"],
                        account["branch_code"],
                    ),
                )


def authenticate_user(
    username: str,
    password: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, object]]:
    """Authenticate credentials and return safe user profile without password hash."""
    clean_username = (username or "").strip().lower()
    if not clean_username or not password:
        return None

    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.password_hash, u.full_name,
                   u.role, u.branch_code, u.is_demo,
                   b.branch_name
            FROM users u
            LEFT JOIN branches b ON u.branch_code = b.branch_code
            WHERE LOWER(u.username) = ?;
            """,
            (clean_username,),
        ).fetchone()

        if row is None or not verify_password(password, row["password_hash"]):
            return None

        log_audit(
            conn,
            username=row["username"],
            action="LOGIN",
            entity_type="user",
            entity_id=str(row["id"]),
            details=f"Role={row['role']}, Branch={row['branch_code'] or 'ALL'}",
        )

        return {
            "id": row["id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
            "branch_code": row["branch_code"],
            "branch_name": row["branch_name"] or "All Branches",
            "is_demo": bool(row["is_demo"]),
        }


def can_access_branch(user: Optional[Dict[str, object]], branch_code: str) -> bool:
    """Return True if the user is Admin or assigned to the target branch."""
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    return user.get("role") == "manager" and user.get("branch_code") == branch_code


def assert_branch_access(user: Optional[Dict[str, object]], branch_code: str) -> None:
    """Raise PermissionError when a user tries to access an unauthorized branch."""
    if not can_access_branch(user, branch_code):
        raise PermissionError(
            f"Access denied: user cannot access branch '{branch_code}'."
        )


def get_allowed_branches(user: Optional[Dict[str, object]]) -> List[str]:
    """Return list of branch codes the user is permitted to access."""
    if not user:
        return []
    if user.get("role") == "admin":
        return [b["branch_code"] for b in MANGALORE_BRANCHES]
    branch_code = user.get("branch_code")
    return [str(branch_code)] if branch_code else []


if __name__ == "__main__":
    seed_branches_and_demo_users()
    admin_user = authenticate_user("admin", "Admin@123")
    hk_user = authenticate_user("hk_manager", "Branch@123")
    bad_login = authenticate_user("hk_manager", "wrongpass")

    assert admin_user is not None and can_access_branch(admin_user, "UR")
    assert hk_user is not None and can_access_branch(hk_user, "HK")
    assert not can_access_branch(hk_user, "KD")
    assert bad_login is None

    print("Auth & RBAC verification passed!")