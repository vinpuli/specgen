"""
SQLAlchemy base model and declarative metadata.

All database models should inherit from this Base class.
"""

from sqlalchemy.orm import DeclarativeBase

from backend.db.meta import metadata


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Models should inherit from this class and define their table
    using __tablename__ attribute.
    """

    metadata = metadata

    def __repr__(self) -> str:
        """
        Generate string representation of the model.

        Override this in subclasses for custom representation.
        """
        attrs = []
        for column in self.__table__.columns:
            if column.primary_key:
                value = getattr(self, column.name, None)
                if value is not None:
                    attrs.append(f"{column.name}={value}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"
