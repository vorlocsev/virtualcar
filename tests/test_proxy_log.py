"""Validate synthetic actual-wrapper output; no private vehicle logs required."""
import json
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
events = [json.loads(line) for line in text.splitlines()]
assert "SYNTHETIC_PRIVATE_PAYLOAD" not in text
assert "987654" in text  # Device timestamp is separately labelled metadata.
diag = [e for e in events if e["schema"] == 46]
assert any(e["relation"] == "filter_time_service_candidate" for e in diag)
assert any(e["event"] == "filter_start" and e["active_filters"] == 1 for e in diag)
assert any(e["rx_pattern_id"] == 0x18DAF150 and e["flow_control_id"] == 0x18DA50F1
           and e["rx_mask_id"] == 0xFFFFFFFF and e["filter_usable"] == 1 for e in diag)
assert any(e["class"] == "uds_read_data_identifier" for e in diag)
assert {e["schema"] for e in events} == {15, 46}
allowed = {"schema", "event", "class", "relation", "ms", "channel", "generation",
           "protocol_id", "baud", "status", "can_id", "size", "rx_status", "tx_flags",
           "device_timestamp_us", "filter_id", "filter_type", "active_filters",
           "incomplete", "sequence", "candidates", "elapsed_ms", "rx_pattern_id",
           "rx_mask_id", "flow_control_id", "filter_usable"}
assert all(set(e) == allowed for e in diag)
print(f"dev46: {len(events)} complete JSON records; metadata-only schema OK")
