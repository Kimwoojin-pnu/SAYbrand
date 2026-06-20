from cardnews.run_log import LogEntry, append_log_entry, load_log_entries, log_event


def test_append_log_entry_stores_single_entry(tmp_path):
    path = tmp_path / "run_log.jsonl"
    entry = LogEntry(timestamp="2026-06-12T00:00:00+00:00", source_id="threat-003", status="generated")

    append_log_entry(path, entry)

    entries = load_log_entries(path)
    assert len(entries) == 1
    assert entries[0] == entry


def test_append_log_entry_stores_multiple_entries(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(path, LogEntry(timestamp="t1", source_id="a", status="generated"))
    append_log_entry(path, LogEntry(timestamp="t2", source_id="b", status="uploaded"))

    entries = load_log_entries(path)
    assert len(entries) == 2
    assert entries[1].source_id == "b"


def test_load_log_entries_returns_empty_list_when_file_missing(tmp_path):
    assert load_log_entries(tmp_path / "missing.jsonl") == []


def test_load_log_entries_parses_existing_entries(tmp_path):
    path = tmp_path / "run_log.jsonl"
    append_log_entry(path, LogEntry(timestamp="t1", source_id="a", status="generated"))
    append_log_entry(path, LogEntry(timestamp="t2", source_id="b", status="uploaded", youtube_video_id="abc123"))

    entries = load_log_entries(path)

    assert entries == [
        LogEntry(timestamp="t1", source_id="a", status="generated"),
        LogEntry(timestamp="t2", source_id="b", status="uploaded", youtube_video_id="abc123"),
    ]


def test_log_event_writes_entry_with_current_timestamp(tmp_path):
    log_event(tmp_path, source_id="threat-003", status="generated", video_path="output/threat-003.mp4")

    entries = load_log_entries(tmp_path / "run_log.jsonl")
    assert len(entries) == 1
    assert entries[0].source_id == "threat-003"
    assert entries[0].status == "generated"
    assert entries[0].video_path == "output/threat-003.mp4"
    assert entries[0].timestamp
