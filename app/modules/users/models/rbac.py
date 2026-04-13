"""
models/rbac.py
==============
Rôles, permissions et associations pour le contrôle d'accès (RBAC).
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Table, Index, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# Table d'association users <-> roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("granted_at", TIMESTAMP, server_default=func.now(), nullable=False),
    Column("granted_by_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
)

# Table d'association roles <-> permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)  # Rôles système non supprimables

    # Relations
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship(
        "User", secondary=user_roles,
        primaryjoin="Role.id==user_roles.c.role_id",
        secondaryjoin="User.id==user_roles.c.user_id",
        back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"<Role(name={self.name})>"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    resource = Column(String(50), nullable=False, index=True)  # users, payments, documents, etc.
    action = Column(String(50), nullable=False, index=True)  # create, read, update, delete, admin

    # Relations
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def __repr__(self) -> str:
        return f"<Permission(name={self.name}, resource={self.resource}:{self.action})>"


# Ajouter la relation roles à User (dans user.py il faut importer ceci)
# User.roles = relationship("Role", secondary=user_roles, back_populates="users")
