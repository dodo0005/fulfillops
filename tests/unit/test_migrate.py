from common.migrate import latest_version, migration_files


def test_migrations_are_found_in_order():
    names = [p.stem for p in migration_files()]
    assert names[:2] == ["001_init", "002_seed"]
    assert names == sorted(names)


def test_latest_version_is_last_file():
    assert latest_version() == migration_files()[-1].stem
