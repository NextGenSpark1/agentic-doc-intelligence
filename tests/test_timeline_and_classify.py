"""Timeline date handling + document classifier heuristic."""
from backend.pipeline.classify import heuristic
from backend.pipeline.reconstruct_timeline import compute_events, parse_date


def test_events_are_sorted_chronologically(sample_extractions):
    events = compute_events(sample_extractions)
    dates = [e["event_date"] for e in events]
    assert dates == sorted(dates)
    assert len(events) == 3  # three payment_dates, no communication dates


def test_parse_date_handles_multiple_formats():
    assert parse_date("2024-06-01") == "2024-06-01"
    assert parse_date("01/06/2024") == "2024-06-01"
    assert parse_date("not a date") is None


def test_classifier_heuristic():
    assert heuristic("INVOICE No: 123  Amount Due: 500") == "invoice"
    assert heuristic("From: a@b.com  Subject: hi  Sent: today") == "email"
