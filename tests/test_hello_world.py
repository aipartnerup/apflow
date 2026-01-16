import pytest
from apflow.core.storage.sqlalchemy.session_proxy import SqlalchemySessionProxy
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def sync_db_session():
    # Setup code for creating a session
    Session = sessionmaker()
    return Session()

def test_set_and_get_hook_context(sync_db_session):
    session = SqlalchemySessionProxy()  # Replace with actual session retrieval logic
    assert session is sync_db_session