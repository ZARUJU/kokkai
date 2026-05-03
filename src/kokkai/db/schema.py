from kokkai.db.base import Base
from kokkai.db.engine import engine

# Import model modules so SQLAlchemy registers their tables on Base.metadata.
from kokkai.models import diet_session  # noqa: F401


def create_all() -> None:
    Base.metadata.create_all(bind=engine)
