from datetime import datetime

from src.infrastructure.persistence.datasource_repository import DatasourceRepository
from src.models.datasource import DatasourceKind, DatasourceRecord


def test_repository_persistence(isolated_env):
    repo = DatasourceRepository()
    record = DatasourceRecord(
        id="ds-1",
        name="sales",
        kind=DatasourceKind.FILE,
        type="csv",
        config={"path": "/tmp/sales.csv"},
        view_names=["sales"],
        created_at=datetime.utcnow(),
    )
    repo.save(record)
    assert repo.get("ds-1") is not None
    assert len(repo.list_all()) == 1

    repo.delete("ds-1")
    assert repo.get("ds-1") is None


def test_repository_reload(isolated_env):
    repo = DatasourceRepository()
    record = DatasourceRecord(
        id="ds-2",
        name="orders",
        kind=DatasourceKind.FILE,
        type="csv",
        config={"path": "/tmp/orders.csv"},
        view_names=["orders"],
        created_at=datetime.utcnow(),
    )
    repo.save(record)

    reloaded = DatasourceRepository()
    assert reloaded.get("ds-2") is not None
    assert reloaded.get("ds-2").name == "orders"
