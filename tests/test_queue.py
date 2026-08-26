from music.queue import QueueError, TrackQueue
from music.track import Track


def track(number: int) -> Track:
    return Track(guild_id=1, webpage_url=f"https://example.test/{number}", title=f"Track {number}")


def test_priority_items_are_first_and_positions_are_one_based():
    queue = TrackQueue(4)
    queue.add(track(1))
    queue.add(track(2), priority=True)
    assert [item.title for item in queue] == ["Track 2", "Track 1"]
    assert queue.position_of(next(iter(queue))) == 1


def test_move_remove_and_shuffle_preserve_all_items():
    queue = TrackQueue(5)
    queue.extend(track(i) for i in range(5))
    queue.move(5, 1)
    assert next(iter(queue)).title == "Track 4"
    removed = queue.remove(2)
    assert removed.title == "Track 0"
    assert {item.title for item in queue} == {"Track 1", "Track 2", "Track 3", "Track 4"}
    queue.shuffle()
    assert {item.title for item in queue} == {"Track 1", "Track 2", "Track 3", "Track 4"}


def test_limits_are_atomic():
    queue = TrackQueue(2)
    with __import__("pytest").raises(QueueError):
        queue.extend([track(1), track(2), track(3)])
    assert len(queue) == 0


def test_pagination_clamps_page():
    queue = TrackQueue(20)
    queue.extend(track(i) for i in range(11))
    items, pages = queue.page(99, 5)
    assert pages == 3
    assert [item.title for _, item in items] == ["Track 10"]
