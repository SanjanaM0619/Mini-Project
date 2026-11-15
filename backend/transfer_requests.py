from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.auth import assert_branch_access
from backend.database import get_connection, log_audit
from backend.transport import calculate_interbranch_cost


def submit_transfer_request(
    user: Dict[str, Any],
    batch_id: str,
    requested_quantity: int,
    reason: str = "",
    db_path: Optional[Path] = None,
) -> int:
    """
    Branch Manager submits a transfer request for their stock.
    Note: Managers do NOT select the destination branch.
    """
    clean_batch_id = (batch_id or "").strip().upper()
    qty = int(requested_quantity)

    if qty <= 0:
        raise ValueError("Requested quantity must be greater than zero.")

    with get_connection(db_path) as conn:
        batch = conn.execute(
            """
            SELECT batch_id, product_code, branch_code, quantity, expiry_date
            FROM inventory_batches
            WHERE UPPER(batch_id) = ?;
            """,
            (clean_batch_id,),
        ).fetchone()

        if not batch:
            raise ValueError(f"Batch '{clean_batch_id}' not found.")

        source_branch = batch["branch_code"]
        assert_branch_access(user, source_branch)

        available_stock = int(batch["quantity"])
        if qty > available_stock:
            raise ValueError(
                f"Requested quantity ({qty}) exceeds available stock ({available_stock})."
            )

        cursor = conn.execute(
            """
            INSERT INTO transfer_requests (
                batch_id, product_code, source_branch,
                requested_quantity, reason, status, requested_by
            )
            VALUES (?, ?, ?, ?, ?, 'Pending', ?);
            """,
            (
                clean_batch_id,
                batch["product_code"],
                source_branch,
                qty,
                reason.strip(),
                user.get("username", "manager"),
            ),
        )
        request_id = int(cursor.lastrowid)

        log_audit(
            conn,
            username=str(user.get("username", "manager")),
            action="SUBMIT_TRANSFER_REQUEST",
            entity_type="transfer_request",
            entity_id=str(request_id),
            details=f"Batch={clean_batch_id}, Qty={qty}, From={source_branch}",
        )
        return request_id


def review_transfer_request(
    admin_user: Dict[str, Any],
    request_id: int,
    action: str,  # 'Approved' or 'Rejected'
    destination_branch: Optional[str] = None,
    admin_note: str = "",
    db_path: Optional[Path] = None,
) -> None:
    """
    Main Admin approves or rejects a transfer request.
    If approved, executes an atomic stock transfer preventing negative inventory.
    """
    if admin_user.get("role") != "admin":
        raise PermissionError("Only Main Admin can review and approve transfer requests.")

    clean_action = action.strip().capitalize()
    if clean_action not in ["Approved", "Rejected"]:
        raise ValueError("Action must be either 'Approved' or 'Rejected'.")

    with get_connection(db_path) as conn:
        req = conn.execute(
            """
            SELECT r.id, r.batch_id, r.product_code, r.source_branch,
                   r.requested_quantity, r.status
            FROM transfer_requests r
            WHERE r.id = ?;
            """,
            (int(request_id),),
        ).fetchone()

        if not req:
            raise ValueError(f"Transfer request #{request_id} not found.")

        if req["status"] != "Pending":
            raise ValueError(f"Request #{request_id} has already been {req['status']}.")

        if clean_action == "Rejected":
            conn.execute(
                """
                UPDATE transfer_requests
                SET status = 'Rejected',
                    admin_note = ?,
                    reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (admin_note.strip(), admin_user.get("username", "admin"), req["id"]),
            )
            log_audit(
                conn,
                username=str(admin_user.get("username", "admin")),
                action="REJECT_TRANSFER",
                entity_type="transfer_request",
                entity_id=str(req["id"]),
                details=f"Note: {admin_note}",
            )
            return

        # Approval requires destination branch
        if not destination_branch:
            raise ValueError("Admin must specify a destination branch to approve the transfer.")

        clean_dest = destination_branch.strip().upper()
        if clean_dest == req["source_branch"]:
            raise ValueError("Destination branch cannot be the same as source branch.")

        # ATOMIC TRANSACTION: update stock and record transfer
        transfer_qty = int(req["requested_quantity"])
        batch_id = req["batch_id"]

        source_batch = conn.execute(
            "SELECT * FROM inventory_batches WHERE batch_id = ?;",
            (batch_id,),
        ).fetchone()

        if not source_batch:
            raise ValueError(f"Source batch '{batch_id}' no longer exists.")

        current_qty = int(source_batch["quantity"])
        if current_qty < transfer_qty:
            raise ValueError(
                f"Insufficient stock in batch '{batch_id}' (available: {current_qty}, requested: {transfer_qty})."
            )

        # 1. Deduct stock from source batch
        new_source_qty = current_qty - transfer_qty
        conn.execute(
            """
            UPDATE inventory_batches
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?;
            """,
            (new_source_qty, batch_id),
        )

        # 2. Add stock to destination batch
        dest_batch_id = f"{batch_id}-TR-{clean_dest}"
        dest_batch = conn.execute(
            "SELECT quantity FROM inventory_batches WHERE batch_id = ?;",
            (dest_batch_id,),
        ).fetchone()

        if dest_batch:
            conn.execute(
                """
                UPDATE inventory_batches
                SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP
                WHERE batch_id = ?;
                """,
                (transfer_qty, dest_batch_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO inventory_batches (
                    batch_id, product_code, branch_code, boxes, units_per_box,
                    quantity, expiry_date, unit_cost, selling_price, is_demo
                )
                VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?, ?);
                """,
                (
                    dest_batch_id,
                    source_batch["product_code"],
                    clean_dest,
                    transfer_qty,
                    source_batch["expiry_date"],
                    source_batch["unit_cost"],
                    source_batch["selling_price"],
                    source_batch["is_demo"],
                ),
            )

        # 3. Calculate transport cost
        cost_info = calculate_interbranch_cost(
            req["source_branch"], clean_dest, quantity=transfer_qty, db_path=db_path
        )
        transport_cost = cost_info["total_transport_cost"]

        # 4. Insert transaction record
        conn.execute(
            """
            INSERT INTO transfer_transactions (
                request_id, source_batch_id, destination_batch_id,
                product_code, from_branch, to_branch,
                quantity_transferred, transport_cost, approved_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                req["id"],
                batch_id,
                dest_batch_id,
                req["product_code"],
                req["source_branch"],
                clean_dest,
                transfer_qty,
                transport_cost,
                admin_user.get("username", "admin"),
            ),
        )

        # 5. Update request status to Approved
        conn.execute(
            """
            UPDATE transfer_requests
            SET status = 'Approved',
                destination_branch = ?,
                admin_note = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (
                clean_dest,
                admin_note.strip(),
                admin_user.get("username", "admin"),
                req["id"],
            ),
        )

        log_audit(
            conn,
            username=str(admin_user.get("username", "admin")),
            action="APPROVE_TRANSFER",
            entity_type="transfer_request",
            entity_id=str(req["id"]),
            details=f"From={req['source_branch']} To={clean_dest}, Qty={transfer_qty}, Cost=₹{transport_cost}",
        )


def get_transfer_requests(
    user: Dict[str, Any],
    status_filter: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return transfer requests filtered by user role and status."""
    role = user.get("role")
    branch_code = user.get("branch_code")

    query = """
        SELECT r.id, r.batch_id, r.product_code, p.product_name,
               r.source_branch, r.destination_branch, r.requested_quantity,
               r.reason, r.status, r.requested_by, r.admin_note,
               r.reviewed_by, r.created_at, r.reviewed_at,
               b.quantity AS current_batch_stock, b.expiry_date,
               b.unit_cost, b.selling_price
        FROM transfer_requests r
        JOIN products p ON r.product_code = p.product_code
        LEFT JOIN inventory_batches b ON r.batch_id = b.batch_id
        WHERE 1 = 1
    """
    params: List[Any] = []

    if role == "manager" and branch_code:
        query += " AND (r.source_branch = ? OR r.destination_branch = ?)"
        params.extend([branch_code, branch_code])

    if status_filter and status_filter != "ALL":
        query += " AND r.status = ?"
        params.append(status_filter)

    query += " ORDER BY r.created_at DESC, r.id DESC;"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    from backend.auth import authenticate_user

    admin = authenticate_user("admin", "Admin@123")
    ur_mgr = authenticate_user("ur_manager", "Branch@123")

    # Manager submits transfer request (source = UR)
    req_id = submit_transfer_request(
        user=ur_mgr,
        batch_id="BATCH-UR-001",
        requested_quantity=20,
        reason="Approaching expiry, low local sales at Urwa",
    )
    assert req_id > 0

    # Admin reviews and approves, choosing Bejai (BJ) as destination
    review_transfer_request(
        admin_user=admin,
        request_id=req_id,
        action="Approved",
        destination_branch="BJ",
        admin_note="Approved based on high Bejai demand.",
    )

    requests = get_transfer_requests(admin, status_filter="Approved")
    assert any(r["id"] == req_id for r in requests)

    print("Transfer request workflow verification passed!")