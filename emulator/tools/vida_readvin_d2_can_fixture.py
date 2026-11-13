"""Synthetic-only original-VIDA D2-on-CAN request framing fixture.

The constants below are derived from static managed-IL inspection of the
owner's VIDA 2014D VehCom2.DLL; this utility does not import proprietary
code, connect to J2534, open a car, or verify real VIDA VIN acceptance.

This is a deterministic *test oracle*, not an emulator implementation.
"""
from __future__ import annotations

CAN_ID_PREFIX = bytes.fromhex('00 0F FF FE')
J2534_CAN_PS_PROTOCOL_ID = 5
J2534_CAN_29BIT_TX_FLAGS = 0x100
J2534_D2_CAN_MESSAGE_SIZE = 12


def make_d2_single_frame(logical_address: int, service_bytes: bytes) -> dict:
    """Return a synthetic J2534 message for one original-VIDA D2 CAN frame.

    The vendor's single-frame format is 0xC8 ORed with the length of the
    logical address plus request, followed by that many bytes and zero fill.
    Data includes a 4-byte CAN identifier and an 8-byte CAN payload.
    """
    if type(logical_address) is not int or not 0 <= logical_address <= 0xFF:
        raise ValueError('logical_address must be an unsigned byte')
    if type(service_bytes) is not bytes or not 1 <= len(service_bytes) <= 6:
        raise ValueError('service_bytes must be 1..6 bytes')
    message = bytes((logical_address,)) + service_bytes
    frame = bytes((0xC8 | len(message),)) + message
    frame += bytes(8 - len(frame))
    data = CAN_ID_PREFIX + frame
    return {
        'protocol_id': J2534_CAN_PS_PROTOCOL_ID,
        'tx_flags': J2534_CAN_29BIT_TX_FLAGS,
        'data_size': J2534_D2_CAN_MESSAGE_SIZE,
        'data': data,
        'source_evidence': 'owner_original_vida_static_il_only',
        'vida_runtime_accepted': False,
        'physical_j2534_tested': False,
    }


def matches_b9_positive_single_frame(frame: bytes, logical_address: int,
                                     block_offset: int) -> bool:
    """Check D2 address, positive B9 service (F9), and requested offset.

    This is an intentionally limited single-frame *synthetic* match, not a
    complete response parser; incoming CAN-ID routing remains unproven.
    """
    if type(frame) is not bytes or len(frame) < 8:
        return False
    if (type(logical_address) is not int or not 0 <= logical_address <= 0xFF
            or type(block_offset) is not int or not 0 <= block_offset <= 0xFF):
        return False
    return ((frame[4] & 0xC0) == 0xC0
            and frame[5] == logical_address
            and frame[6] == 0xF9
            and frame[7] == block_offset)
