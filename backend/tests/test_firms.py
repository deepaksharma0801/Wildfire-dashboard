from app.firms import (
    ARIZONA_BBOX,
    build_firms_area_url,
    confidence_to_score,
    dedupe_features,
    normalize_firms_csv,
    parse_acq_datetime,
)


CSV_TEXT = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
34.2439,-111.3289,322.2,0.39,0.36,2026-05-19,636,N,VIIRS,n,2.0NRT,301.1,9.7,D
34.2439,-111.3289,322.2,0.39,0.36,2026-05-19,0636,N,VIIRS,n,2.0NRT,301.1,9.7,D
35.1983,-111.6513,333.8,0.41,0.38,2026-05-20,1912,N20,VIIRS,h,2.0NRT,306.4,18.4,D
"""


def test_build_firms_area_url() -> None:
    url = build_firms_area_url(
        map_key="abc123",
        source="VIIRS_SNPP_NRT",
        bbox=ARIZONA_BBOX,
        day_range=3,
        date="2026-05-20",
    )

    assert url.endswith("/abc123/VIIRS_SNPP_NRT/-115.1,31.2,-108.8,37.1/3/2026-05-20")


def test_confidence_scores_accept_viirs_labels() -> None:
    assert confidence_to_score("l") == (30, "l")
    assert confidence_to_score("n") == (60, "n")
    assert confidence_to_score("h") == (90, "h")
    assert confidence_to_score("92") == (92, "92")


def test_parse_acq_datetime_pads_time() -> None:
    assert parse_acq_datetime("2026-05-19", "636") == "2026-05-19T06:36:00Z"


def test_normalize_firms_csv_dedupes_and_sorts() -> None:
    collection = normalize_firms_csv(CSV_TEXT, source="VIIRS_SNPP_NRT")

    assert collection["metadata"]["count"] == 2
    assert collection["features"][0]["properties"]["confidence"] == 90
    assert collection["features"][0]["properties"]["sample"] is False
    assert collection["features"][1]["properties"]["acq_time"] == "0636"


def test_dedupe_features_keeps_unique_detections() -> None:
    collection = normalize_firms_csv(CSV_TEXT, source="VIIRS_SNPP_NRT")
    deduped = dedupe_features(collection["features"] + collection["features"])

    assert len(deduped) == 2
