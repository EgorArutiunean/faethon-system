from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.identity import Permission, Role, User
from app.services.currency_service import seed_default_currencies


PERMISSIONS = [
    "products.read",
    "products.create",
    "products.update",
    "products.delete",
    "warehouses.read",
    "warehouses.create",
    "warehouses.update",
    "warehouses.delete",
    "partners.read",
    "partners.create",
    "partners.update",
    "partners.delete",
    "documents.read",
    "documents.create",
    "documents.update",
    "documents.delete",
    "documents.post",
    "documents.cancel",
    "stock.read",
    "payments.read",
    "payments.create",
    "payments.update",
    "payments.delete",
    "payments.post",
    "payments.cancel",
    "cash.read",
    "cash.create",
    "cash.cancel",
    "reports.read",
    "audit.read",
    "users.manage",
    "settings.manage",
]


ROLE_PERMISSIONS = {
    "admin": PERMISSIONS,
    "manager": [
        "products.read",
        "products.create",
        "products.update",
        "warehouses.read",
        "warehouses.create",
        "warehouses.update",
        "partners.read",
        "partners.create",
        "partners.update",
        "documents.read",
        "documents.create",
        "documents.update",
        "documents.delete",
        "documents.post",
        "documents.cancel",
        "stock.read",
        "reports.read",
    ],
    "cashier": [
        "partners.read",
        "payments.read",
        "payments.create",
        "payments.update",
        "payments.delete",
        "payments.post",
        "payments.cancel",
        "cash.read",
        "cash.create",
        "cash.cancel",
        "reports.read",
    ],
    "viewer": [
        "products.read",
        "warehouses.read",
        "partners.read",
        "documents.read",
        "stock.read",
        "payments.read",
        "cash.read",
        "reports.read",
    ],
}


def seed_auth_defaults(db: Session) -> User:
    seed_default_currencies(db)

    permissions_by_code: dict[str, Permission] = {}
    for code in PERMISSIONS:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=code)
            db.add(permission)
        permissions_by_code[code] = permission
    db.flush()

    roles_by_name: dict[str, Role] = {}
    for name, codes in ROLE_PERMISSIONS.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=f"{name} role")
            db.add(role)
        role.permissions = [permissions_by_code[code] for code in codes]
        roles_by_name[name] = role
    db.flush()

    demo_users = [
        ("admin@example.com", "admin123", "Demo Admin", "admin"),
        ("manager@example.com", "manager123", "Demo Manager", "manager"),
        ("cashier@example.com", "cashier123", "Demo Cashier", "cashier"),
        ("viewer@example.com", "viewer123", "Demo Viewer", "viewer"),
    ]
    admin: User | None = None
    for email, password, full_name, role_name in demo_users:
        user = db.scalar(select(User).where(User.username == email))
        if user is None:
            user = User(
                username=email,
                full_name=full_name,
                is_active=True,
            )
            db.add(user)
        user.full_name = full_name
        user.hashed_password = hash_password(password)
        user.is_active = True
        user.roles = [roles_by_name[role_name]]
        if role_name == "admin":
            admin = user
    db.commit()
    assert admin is not None
    db.refresh(admin)
    return admin
