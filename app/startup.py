from pathlib import Path

from app.config import SEED_FILE
from app.dependencies import get_access_repository, get_batch_repository
from app.loaders.seed_loader import load_seed
from app.services.access import AccessService


def seed_directory() -> None:
    """Load the seed file into SQLite; a bad seed raises SeedError, so the server does not start."""
    seed = load_seed(Path(SEED_FILE))
    AccessService(get_access_repository(), get_batch_repository()).seed(seed)
