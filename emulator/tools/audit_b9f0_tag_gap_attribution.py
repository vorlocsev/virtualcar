"""Classify native P2 D2 J2534 delivery-tag adjacency without leaking data.

This is the same strict same-PID adjacency rule as _native_d2_delivery_tags,
with mutually exclusive categorical reasons. NOT B9F0-specific attribution.
"""
from collections import Counter
import re
from audit_j2534_discovery import PREFIX, _context

RX_CONTEXT = "RX context channel/protocol/status/baud/time-us (BE)"
RX_DELIVERY = "PassThruReadMsgs -> delivered"
D2_DELIVERY = "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)"
RAW_CAN = re.compile(r"(?:[0-9A-Fa-f]{2}\s+){11}[0-9A-Fa-f]{2}")


class TagGapAttribution:
    def __init__(self):
        self.scopes = {}
        self.counts = Counter()
        self.missing_context_reasons = Counter()
        self.non_can_protocols = Counter()

    @staticmethod
    def _interruption(event):
        if event.startswith("P2_HW_RX_"):
            return "unpaired_intervening_hardware_observer"
        if event.startswith("P2 D2 "):
            return "unpaired_intervening_d2_event"
        if event.startswith(("PassThru", "J2534 ")):
            return "unpaired_intervening_j2534_event"
        return "unpaired_intervening_other_same_pid_event"

    def observe(self, line):
        match = PREFIX.match(line)
        if match is None:
            return
        pid, event = match.group(1), match.group(2).rstrip("\r\n")
        scope = self.scopes.setdefault(pid, {
            "ctx": None, "pending": None, "cause": "unpaired_no_prior_rx",
            "missing_context_reason": None
        })
        if event.startswith(("PassThruOpen ->", "PassThruClose",
                             "PassThruDisconnect")):
            scope.update(ctx=None, pending=None,
                         cause="unpaired_session_or_channel_boundary",
                         missing_context_reason=None)
            return
        if event.startswith("RX context "):
            ctx = _context(event, RX_CONTEXT, True)
            scope.update(ctx=ctx, pending=None,
                         cause=("unpaired_rx_context_without_delivery" if ctx
                                else "unpaired_invalid_rx_context"),
                         missing_context_reason=None)
            return
        if event.startswith(RX_DELIVERY):
            suffix = event[len(RX_DELIVERY):].strip()
            raw = bytes.fromhex(suffix) if RAW_CAN.fullmatch(suffix) else None
            ctx = scope["ctx"]
            scope["ctx"] = None
            if ctx is None:
                # Retain the PRE-delivery reason. The existing primary
                # category is deliberately unchanged for compatibility.
                predecessor = scope["cause"]
                if predecessor not in (
                        "unpaired_no_prior_rx",
                        "unpaired_invalid_rx_context",
                        "unpaired_session_or_channel_boundary",
                        "unpaired_intervening_hardware_observer",
                        "unpaired_intervening_d2_event",
                        "unpaired_intervening_j2534_event",
                        "unpaired_intervening_other_same_pid_event"):
                    predecessor = "unpaired_other_unverified_predecessor"
                scope.update(
                    pending=None,
                    cause="unpaired_delivery_without_valid_rx_context",
                    missing_context_reason=predecessor)
            elif raw is None:
                scope.update(pending=None,
                             cause="unpaired_nonclassic_or_invalid_rx_record",
                             missing_context_reason=None)
            else:
                scope.update(pending=(ctx, raw),
                             cause="unpaired_pending_rx_without_tag",
                             missing_context_reason=None)
            return
        if event.startswith("P2 D2 delivered "):
            metadata = _context(event, D2_DELIVERY, True)
            pending = scope["pending"]
            scope["ctx"] = scope["pending"] = None
            cause = scope["cause"]
            missing_reason = scope["missing_context_reason"]
            scope["cause"] = "unpaired_no_prior_rx"
            scope["missing_context_reason"] = None
            if metadata is None:
                category = "malformed_tag"
            elif pending is None:
                category = cause
                if category == "unpaired_delivery_without_valid_rx_context":
                    self.missing_context_reasons[
                        missing_reason or "unpaired_other_unverified_predecessor"] += 1
            else:
                ctx, raw = pending
                channel, generation, frame, _rx_us, _delivery_us = metadata
                if channel == 0 or generation == 0 or not 1 <= frame <= 64:
                    category = "mismatch_invalid_generation_or_frame"
                elif channel != ctx[0]:
                    category = "mismatch_channel"
                elif ctx[1] != 5:
                    category = "mismatch_protocol_not_can"
                    self.non_can_protocols[
                        "ISO15765_6" if ctx[1] == 6 else "other_non_CAN"] += 1
                elif ctx[3] == 0:
                    category = "mismatch_zero_baud"
                elif ctx[2] & 0x0B:
                    category = "mismatch_rx_status"
                elif raw is None or len(raw) != 12:
                    category = "mismatch_rx_length"
                else:
                    category = "paired_strict_native_rx_tag"
            self.counts[category] += 1
            return
        if scope["ctx"] is not None or scope["pending"] is not None:
            scope.update(ctx=None, pending=None,
                         cause=self._interruption(event),
                         missing_context_reason=None)

    def summary(self, shared):
        paired = self.counts["paired_strict_native_rx_tag"]
        mismatched = sum(n for k, n in self.counts.items()
                         if k.startswith("mismatch_"))
        unpaired = sum(n for k, n in self.counts.items()
                       if k.startswith("unpaired_"))
        verified_reconciliation = (
            paired == shared["paired_tag_records"]
            and mismatched == shared["route_or_metadata_mismatch"]
            and unpaired == shared["unpaired_tag_records"]
            and self.counts["malformed_tag"] == shared["malformed_tag_records"]
            and sum(self.counts.values()) == shared["tag_records"]
        )
        return {
            "scope": "categorical_same_pid_native_rx_adjacency_only",
            "categories": dict(sorted(self.counts.items())),
            "total_tag_records_classified": sum(self.counts.values()),
            "category_totals_agree_with_legacy_auditor": verified_reconciliation,
            "missing_rx_context_predecessor_categories": dict(
                sorted(self.missing_context_reasons.items())),
            "missing_rx_context_predecessor_counts_reconcile": (
                sum(self.missing_context_reasons.values())
                == self.counts["unpaired_delivery_without_valid_rx_context"]),
            "non_CAN_protocol_categories": dict(
                sorted(self.non_can_protocols.items())),
            "non_CAN_protocol_counts_reconcile": (
                sum(self.non_can_protocols.values())
                == self.counts["mismatch_protocol_not_can"]),
            "b9f0_specific_causal_attribution_verified": False,
            "notes": [
                "Missing strict logger adjacency does not prove a lost J2534 frame.",
                "This is all D2 generation tags, not proven per-command B9F0 traffic.",
                "Predecessor categories describe why the logger parser lacked a valid RX context immediately before a delivery record.",
                "J2534 protocol 6 denotes ISO15765 metadata but is not by itself evidence of a D2 message sent over ISO15765.",
                "No raw CAN, VIN, PID, path, timestamp or secret appears in the report.",
            ],
        }
