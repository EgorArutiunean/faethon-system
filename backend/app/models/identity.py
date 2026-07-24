from sqlalchemy import Boolean, ForeignKey, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

user_warehouses = Table(
    "user_warehouses",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("warehouse_id", ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True),
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")
    warehouses: Mapped[list["Warehouse"]] = relationship(secondary=user_warehouses, back_populates="users")

    @property
    def email(self) -> str:
        return self.username

    @property
    def role_names(self) -> list[str]:
        return [role.name for role in self.roles]

    @property
    def permissions(self) -> list[str]:
        codes: set[str] = set()
        for role in self.roles:
            codes.update(permission.code for permission in role.permissions)
        return sorted(codes)

    @property
    def warehouse_ids(self) -> list[int]:
        return [warehouse.id for warehouse in self.warehouses]

    @property
    def warehouse_names(self) -> list[str]:
        return [warehouse.name for warehouse in self.warehouses]


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")
