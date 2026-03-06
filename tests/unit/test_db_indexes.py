from app.models.job import Job


def _index_names():
    return {idx.name for idx in Job.__table__.indexes}


def _index_columns(index_name: str):
    for idx in Job.__table__.indexes:
        if idx.name == index_name:
            return [col.name for col in idx.columns]
    return []


# index existence
def test_status_index_exists():
    assert "idx_jobs_status" in _index_names()


def test_created_at_index_exists():
    assert "idx_jobs_created_at" in _index_names()


def test_status_created_at_composite_index_exists():
    assert "idx_jobs_status_created_at" in _index_names()


def test_last_attempt_at_index_exists():
    assert "idx_jobs_last_attempt_at" in _index_names()


# index column correctness
def test_status_index_covers_status_column():
    cols = _index_columns("idx_jobs_status")
    assert "status" in cols


def test_created_at_index_covers_created_at_column():
    cols = _index_columns("idx_jobs_created_at")
    assert "created_at" in cols


def test_composite_index_covers_both_columns():
    cols = _index_columns("idx_jobs_status_created_at")
    assert "status" in cols
    assert "created_at" in cols


def test_last_attempt_at_index_covers_last_attempt_at_column():
    cols = _index_columns("idx_jobs_last_attempt_at")
    assert "last_attempt_at" in cols


# index count sanity check
def test_at_least_four_custom_indexes():
    custom = {
        n for n in _index_names()
        if n.startswith("idx_jobs_")
    }
    assert len(custom) >= 4, f"Expected ≥4 custom indexes, found: {custom}"
