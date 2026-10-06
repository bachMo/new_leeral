from app import models
from app.db.base import Base

metadata = Base.metadata

__all__ = ["metadata", "models"]
