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
        self.other_protocol_values = Counter()
        self.wide_protocol_shapes = Counter()
        self.no_prior_previous_event_classes = Counter()

    @staticmethod
    def _interruption(event):
        if event.startswith("P2_HW_RX_"):
            return "unpaired_intervening_hardware_observer"
        if event.startswith("P2 D2 "):
            return "unpaired_intervening_d2_event"
        if event.startswith(("PassThru", "J2534 ")):
            return "unpaired_intervening_j2534_event"
        return "unpaired_intervening_other_same_pid_event"

    @staticmethod
    def _event_class(event):
        # Bounded fixed labels only; do not export native event text.
        if event.startswith("RX context "):
            return "rx_context"
        if event.startswith(RX_DELIVERY):
            return "rx_delivery"
        if event.startswith("P2 D2 delivered "):
            return "d2_delivery_tag"
        # These bounded labels are emitted by the current DLL's RX observer.
        # They can interrupt a strict RX-delivery/tag chain, not prove frame loss.
        if event.startswith("P2_HW_RX_"):
            return "hardware_rx_observer"
        if event.startswith("P2_HW_"):
            return "hardware_other_observer"
        if event.startswith("TX context "):
            return "tx_context"
        if event.startswith("TX (app request)"):
            return "tx_request"
        if event.startswith("Periodic TX context "):
            return "periodic_tx_context"
        if event.startswith("CLEAR_RX context "):
            return "clear_rx_context"
        if event.startswith("PassThruOpen ->"):
            return "open_boundary"
        if event.startswith("PassThruClose"):
            return "close_boundary"
        if event.startswith("PassThruDisconnect"):
            return "disconnect_boundary"
        if event.startswith("P2 D2 request "):
            return "d2_request"
        if event.startswith("P2 D2 "):
            return "other_d2_marker"
        if event.startswith("PassThru"):
            return "other_passthru_marker"
        if event.startswith("J2534"):
            return "other_j2534_marker"
        return "other_native_event"

    @staticmethod
    def _protocol_value_class(protocol):
        # J2534 protocol numbers are public enums, but bound output to
        # known small categorical values; never export an arbitrary word.
        return ("protocol_" + str(protocol)
                if 0 <= protocol <= 12 else "other_protocol_value")

    @staticmethod
    def _wide_protocol_shape(protocol):
        # Public metadata only, but never return a source-specific arbitrary
        # 32-bit word. Shape is not proof of a byte-order or memory defect.
        if protocol in (0x05000000, 0x06000000):
            return "byte_swapped_known_id_shape"
        if protocol == 0xFFFFFFFF:
            return "all_bits_set"
        if protocol <= 0xFFFF:
            return "other_16bit_value"
        if (protocol & 0xFFFF) == 0:
            return "low_word_zero"
        return "other_32bit_value"

    def observe(self, line):
        match = PREFIX.match(line)
        if match is None:
            return
        pid, event = match.group(1), match.group(2).rstrip("\r\n")
        scope = self.scopes.setdefault(pid, {
            "ctx": None, "pending": None, "cause": "unpaired_no_prior_rx",
            "missing_context_reason": None,
            "prior_delivery_event_class": None,
            "last_event_class": "none"
        })
        previous_class = scope["last_event_class"]
        scope["last_event_class"] = self._event_class(event)
        if event.startswith(("PassThruOpen ->", "PassThruClose",
                             "PassThruDisconnect")):
            scope.update(ctx=None, pending=None,
                         cause="unpaired_session_or_channel_boundary",
                         missing_context_reason=None,
                         prior_delivery_event_class=None)
            return
        if event.startswith("RX context "):
            ctx = _context(event, RX_CONTEXT, True)
            scope.update(ctx=ctx, pending=None,
                         cause=("unpaired_rx_context_without_delivery" if ctx
                                else "unpaired_invalid_rx_context"),
                         missing_context_reason=None,
                         prior_delivery_event_class=None)
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
                    missing_context_reason=predecessor,
                    prior_delivery_event_class=previous_class)
            elif raw is None:
                scope.update(pending=None,
                             cause="unpaired_nonclassic_or_invalid_rx_record",
                             missing_context_reason=None,
                             prior_delivery_event_class=None)
            else:
                scope.update(pending=(ctx, raw),
                             cause="unpaired_pending_rx_without_tag",
                             missing_context_reason=None,
                             prior_delivery_event_class=None)
            return
        if event.startswith("P2 D2 delivered "):
            metadata = _context(event, D2_DELIVERY, True)
            pending = scope["pending"]
            scope["ctx"] = scope["pending"] = None
            cause = scope["cause"]
            missing_reason = scope["missing_context_reason"]
            missing_previous_class = scope["prior_delivery_event_class"]
            scope["cause"] = "unpaired_no_prior_rx"
            scope["missing_context_reason"] = None
            scope["prior_delivery_event_class"] = None
            if metadata is None:
                category = "malformed_tag"
            elif pending is None:
                category = cause
                if category == "unpaired_delivery_without_valid_rx_context":
                    self.missing_context_reasons[
                        missing_reason or "unpaired_other_unverified_predecessor"] += 1
                    if missing_reason == "unpaired_no_prior_rx":
                        self.no_prior_previous_event_classes[
                            missing_previous_class or "none"] += 1
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
                    if ctx[1] != 6:
                        self.other_protocol_values[
                            self._protocol_value_class(ctx[1])] += 1
                        if ctx[1] > 12:
                            self.wide_protocol_shapes[
                                self._wide_protocol_shape(ctx[1])] += 1
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
                         missing_context_reason=None,
                         prior_delivery_event_class=None)

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
            "non_CAN_other_protocol_values": dict(
                sorted(self.other_protocol_values.items())),
            "non_CAN_other_values_reconcile": (
                sum(self.other_protocol_values.values())
                == self.non_can_protocols["other_non_CAN"]),
            "non_CAN_wide_protocol_shapes": dict(
                sorted(self.wide_protocol_shapes.items())),
            "non_CAN_wide_protocol_shapes_reconcile": (
                sum(self.wide_protocol_shapes.values())
                == self.other_protocol_values["other_protocol_value"]),
            "no_prior_rx_previous_event_classes": dict(
                sorted(self.no_prior_previous_event_classes.items())),
            "no_prior_rx_previous_events_reconcile": (
                sum(self.no_prior_previous_event_classes.values())
                == self.missing_context_reasons["unpaired_no_prior_rx"]),
            "b9f0_specific_causal_attribution_verified": False,
            "notes": [
                "Missing strict logger adjacency does not prove a lost J2534 frame.",
                "This is all D2 generation tags, not proven per-command B9F0 traffic.",
                "Predecessor categories describe why the logger parser lacked a valid RX context immediately before a delivery record.",
                "J2534 protocol 6 denotes ISO15765 metadata but is not by itself evidence of a D2 message sent over ISO15765.",
                "Previous event class is only the most recent same-PID native logger event; it is not a verified transaction boundary.",
                "A protocol number in RX metadata is not proof of a physical bus or original SectorV client behavior.",
                "The current emulator accepts only protocol 5/6 at Connect; wide RX protocol metadata require checking the exact DLL version and log integrity.",
                "Known observer classes and numeric word shapes do not reclassify any unpaired or mismatched D2 delivery as successfully paired.",
                "No raw CAN, VIN, PID, path, timestamp or secret appears in the report.",
            ],
        }
