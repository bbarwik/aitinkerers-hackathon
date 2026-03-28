from gamesight.video.chunker import compute_chunks


def test_compute_chunks_ownership_windows() -> None:
    chunks = compute_chunks(1320.0, youtube_url="https://www.youtube.com/watch?v=demo")

    assert len(chunks) == 6
    assert chunks[0].start_seconds == 0.0
    assert chunks[0].end_seconds == 300.0
    assert chunks[0].owns_from == 0.0
    assert chunks[0].owns_until == 270.0
    assert chunks[1].start_seconds == 240.0
    assert chunks[1].owns_from == 270.0
    assert chunks[1].owns_until == 510.0
    assert chunks[-1].owns_until == 1320.0

