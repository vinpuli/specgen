"""
Database metadata and utilities.

This module exports the SQLAlchemy metadata object that is used
by all models to define their tables and relationships.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Define naming conventions for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create metadata with naming conventions
metadata = MetaData(naming_convention=convention)


# Common timestamp columns for audit trails
timestamps = {
    "created_at": (func.now(), "created_at"),
    "updated_at": (func.now(), "updated_at"),
}
