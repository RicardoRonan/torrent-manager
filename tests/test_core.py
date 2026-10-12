from app import aria2, config, store


def test_derive_name_from_torrent_info():
    item = {"gid": "1", "bittorrent": {"info": {"name": "Big Buck Bunny"}}}
    assert aria2.derive_name(item) == "Big Buck Bunny"


def test_derive_name_from_files():
    item = {"gid": "1", "files": [{"path": "/tmp/downloads/film.mkv"}]}
    assert aria2.derive_name(item) == "film.mkv"


def test_derive_state_metadata():
    assert aria2.derive_state({"status": "active", "totalLength": "0"}) == "metadata"


def test_derive_state_downloading_and_complete():
    assert aria2.derive_state({"status": "active", "totalLength": "100", "completedLength": "40"}) == "downloading"
    assert aria2.derive_state({"status": "complete"}) == "complete"
    assert aria2.derive_state({"status": "paused"}) == "paused"
    assert aria2.derive_state({"status": "waiting"}) == "queued"
    assert aria2.derive_state({"status": "error"}) == "error"


def test_normalize_computes_progress_speed_eta():
    raw = {
        "gid": "g1",
        "status": "active",
        "totalLength": "1000",
        "completedLength": "250",
        "uploadLength": "500",
        "downloadSpeed": "125",
        "uploadSpeed": "10",
        "connections": "12",
        "numSeeders": "3",
        "files": [{"path": "/d/a.bin"}],
    }
    item = aria2.normalize(raw, {"category": "Movies", "tags": ["x"]})
    assert item["percent"] == 25.0
    assert item["eta"] == 6
    assert item["ratio"] == 2.0
    assert item["connections"] == 12
    assert item["seeds"] == 3
    assert item["category"] == "Movies"
    assert item["tags"] == ["x"]


def test_settings_seed_is_forced_off():
    updated = store.update_settings({"seed_time": 30, "seed_ratio": 1.5})
    assert updated["seed_time"] == 0
    assert updated["seed_ratio"] == 0.0


def test_settings_partial_merge_preserves_others():
    updated = store.update_settings({"theme": "light"})
    assert updated["theme"] == "light"
    assert "max_concurrent" in updated
    assert updated["seed_time"] == 0


def test_meta_record_resolve_and_promote():
    store.record_meta("gid-a", category="TV", tags=["a"], added_at=1.0)
    resolved = store.resolve_meta({"gid": "gid-a"})
    assert resolved["category"] == "TV"
    assert resolved["tags"] == ["a"]

    store.promote_meta("gid-a", "ABCDEF")
    by_hash = store.resolve_meta({"gid": "other", "infoHash": "abcdef"})
    assert by_hash["category"] == "TV"


def test_perf_presets_defined():
    for name in ("conservative", "balanced", "aggressive"):
        assert name in config.PERF_PRESETS
        assert "bt_max_peers" in config.PERF_PRESETS[name]


def test_build_cmd_includes_performance_flags():
    client = aria2.Aria2Client()
    cmd = " ".join(client._build_cmd(store.get_settings()))
    assert "--bt-max-peers=128" in cmd
    assert "--disk-cache=64M" in cmd
    assert "--file-allocation=falloc" in cmd
    assert "--optimize-concurrent-downloads=true" in cmd
    assert "--lowest-speed-limit=10K" in cmd
    assert "--seed-time=0" in cmd

