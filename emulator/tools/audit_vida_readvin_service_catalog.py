#!/usr/bin/env python3
"""Bounded, read-only VIDA ReadVin.ServiceId vs T111_Service catalog classification.

Static candidate only. Input source identifiers and service definitions never
leave the process, and no wire request, valid ECU reply or VIN is inferred.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = 'virtualcar-vida-readvin-service-catalog-static-v1'
MAX_ZIP_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 1024 * 1024
MAX_CSV_BYTES = 4 * 1024 * 1024
MAX_SERVICE_DEFINITION_BYTES = 1024 * 1024
MAX_ELEMENTS = 20000
MAX_DEPTH = 96  # Matches the bounded original-IL XML classifier.
MAX_ROWS = 50000
MAX_CSV_LINE_LENGTH = 65536
_NUMBER = re.compile(r'(?:0|[1-9][0-9]{0,9})\Z')


def _positive_id(value):
    if value is None or not _NUMBER.fullmatch(value):
        return None
    n = int(value)
    return n if 0 <= n <= 2147483647 else None


def _parse_xml(xml_bytes):
    if (not isinstance(xml_bytes, bytes) or len(xml_bytes) > MAX_XML_BYTES
            or b'\x00' in xml_bytes[:256]
            or xml_bytes.startswith((b'\xff\xfe', b'\xfe\xff'))
            or re.search(rb'<!\s*(?:DOCTYPE|ENTITY)\b', xml_bytes, re.I)):
        raise ValueError('unsafe XML')
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError('invalid XML') from exc
    if root.tag != 'script' or len(root.findall('./content')) != 1:
        raise ValueError('unexpected script structure')
    content = root.find('./content')
    nodes = content.findall('./nodes/node')
    handlers = content.findall('./handlers/eventhandler')
    if not nodes or not handlers:
        raise ValueError('missing script nodes or handlers')
    # Iterative depth check avoids recursion and rejects XML structures that
    # the original SHA-pinned parser's bounded audit cannot safely classify.
    pending = [(root, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ValueError('excessive XML complexity')
        pending.extend((child, depth + 1) for child in item)
    ids = [n.attrib.get('nodeid', '') for n in nodes]
    if any(not i or len(i) > 128 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('unsafe or duplicate node identifiers')
    return content, nodes


def _parse_service_definition(data):
    """Read only the exporter's <service id="..."> wrapper, never its payload."""
    if (not isinstance(data, bytes) or not data or
            len(data) > MAX_SERVICE_DEFINITION_BYTES or
            b'\x00' in data[:256] or
            data.startswith((b'\xff\xfe', b'\xfe\xff')) or
            re.search(rb'<!\s*(?:DOCTYPE|ENTITY)\b', data, re.I)):
        raise ValueError('unsafe service definition XML')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError('invalid service definition XML') from exc
    if root.tag != 'service':
        raise ValueError('unexpected service definition root')
    service_id = _positive_id(root.attrib.get('id'))
    if service_id is None:
        raise ValueError('invalid service definition id')
    pending = [(root, 0)]
    count = 0
    content_present = False
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ValueError('excessive service definition complexity')
        if node is not root or (node.text and node.text.strip()):
            content_present = True
        pending.extend((child, depth + 1) for child in node)
    # Empty root has no definition; fail closed rather than treating it as evidence.
    if not content_present:
        raise ValueError('empty service definition')
    return service_id, True


def _parse_catalog(csv_bytes):
    if (not isinstance(csv_bytes, bytes) or len(csv_bytes) > MAX_CSV_BYTES
            or b'\x00' in csv_bytes):
        raise ValueError('unsafe CSV')
    try:
        text = csv_bytes.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('unsupported CSV encoding') from exc
    if any(len(line) > MAX_CSV_LINE_LENGTH for line in text.splitlines()):
        raise ValueError('CSV line too long')
    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    # An arbitrary CSV with an id column is not sufficient to establish
    # the documented T111_Service schema. This is still NOT provenance proof.
    if (not reader.fieldnames or
            not {'id', 'service', 'mode'}.issubset(reader.fieldnames) or
            len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError('expected unique T111 service catalog headers')
    occurrences = {}
    metadata_complete_ids = {}
    protocol_complete_ids = {}
    protocol_keys_by_service_id = {}
    has_protocol_header = 'fkT122_Protocol' in reader.fieldnames
    total = invalid = empty_metadata = 0
    try:
        for record in reader:
            total += 1
            if (total > MAX_ROWS or None in record or
                    any(v is None for v in record.values())):
                raise ValueError('invalid CSV structure')
            has_metadata = bool(record['service'].strip() and record['mode'].strip())
            if not has_metadata:
                empty_metadata += 1
            value = _positive_id(record.get('id'))
            if value is None:
                invalid += 1
            else:
                occurrences[value] = occurrences.get(value, 0) + 1
                if has_metadata:
                    metadata_complete_ids[value] = metadata_complete_ids.get(value, 0) + 1
                    if has_protocol_header:
                        protocol_key = _positive_id(record['fkT122_Protocol'])
                        if protocol_key is not None:
                            protocol_complete_ids[value] = protocol_complete_ids.get(value, 0) + 1
                            protocol_keys_by_service_id[value] = protocol_key
    except (csv.Error, UnicodeError) as exc:
        raise ValueError('malformed CSV') from exc
    return occurrences, metadata_complete_ids, protocol_complete_ids, protocol_keys_by_service_id, total, invalid, empty_metadata



def _parse_protocol_catalog(csv_bytes):
    """Bounded T122_Protocol FK classification; never exposes protocol names."""
    if (not isinstance(csv_bytes, bytes) or len(csv_bytes) > MAX_CSV_BYTES
            or b'\x00' in csv_bytes):
        raise ValueError('unsafe T122 CSV')
    try:
        text = csv_bytes.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('unsupported T122 CSV encoding') from exc
    if any(len(line) > MAX_CSV_LINE_LENGTH for line in text.splitlines()):
        raise ValueError('T122 CSV line too long')
    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    # Original T122_Protocol export uses id and identifier; a numeric ID
    # without an actual protocol identifier is not a valid FK target.
    if (not reader.fieldnames or
            not {'id', 'identifier'}.issubset(reader.fieldnames) or
            len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError('expected unique T122 id and identifier headers')
    ids = set()
    try:
        for row_number, record in enumerate(reader, 1):
            if (row_number > MAX_ROWS or None in record or
                    any(v is None for v in record.values())):
                raise ValueError('invalid T122 CSV row structure')
            key = _positive_id(record['id'])
            if key is None or not record['identifier'].strip() or key in ids:
                raise ValueError('invalid or duplicate T122 protocol record')
            ids.add(key)
    except (csv.Error, UnicodeError) as exc:
        raise ValueError('malformed T122 CSV') from exc
    if not ids:
        raise ValueError('empty T122 protocol catalog')
    return ids

def _parse_service_ecu_variant_map(csv_bytes):
    """Validate original T110 relationship table; return private FK pairs only."""
    if (not isinstance(csv_bytes, bytes) or len(csv_bytes) > MAX_CSV_BYTES
            or b'\x00' in csv_bytes):
        raise ValueError('unsafe T110 CSV')
    try:
        data = csv_bytes.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('unsupported T110 CSV encoding') from exc
    if any(len(line) > MAX_CSV_LINE_LENGTH for line in data.splitlines()):
        raise ValueError('T110 CSV line too long')
    reader = csv.DictReader(io.StringIO(data, newline=''), strict=True)
    if (not reader.fieldnames or
            not {'fkT100_EcuVariant', 'fkT111_Service'}.issubset(reader.fieldnames) or
            len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError('expected T110 foreign-key columns')
    pairs = set()
    try:
        for row_index, record in enumerate(reader, 1):
            if (row_index > MAX_ROWS or None in record or
                    any(value is None for value in record.values())):
                raise ValueError('invalid T110 row structure')
            variant = _positive_id(record['fkT100_EcuVariant'])
            service = _positive_id(record['fkT111_Service'])
            if (variant is None or variant == 0 or service is None or service == 0
                    or (variant, service) in pairs):
                raise ValueError('invalid or duplicate T110 relationship')
            pairs.add((variant, service))
    except (csv.Error, UnicodeError) as exc:
        raise ValueError('malformed T110 CSV') from exc
    if not pairs:
        raise ValueError('empty T110 catalog')
    return pairs



def _bounded_fk_rows(csv_bytes, required_columns):
    """Private bounded SQL-export CSV; reject duplicate/ambiguous headers."""
    if (not isinstance(csv_bytes, bytes) or len(csv_bytes) > MAX_CSV_BYTES
            or b'\x00' in csv_bytes):
        raise ValueError('unsafe profile CSV')
    try:
        text = csv_bytes.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('unsupported profile CSV encoding') from exc
    if any(len(line) > MAX_CSV_LINE_LENGTH for line in text.splitlines()):
        raise ValueError('profile CSV line too long')
    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    if (not reader.fieldnames or not required_columns.issubset(reader.fieldnames)
            or len(set(reader.fieldnames)) != len(reader.fieldnames)):
        raise ValueError('missing or duplicate profile CSV headers')
    rows = []
    try:
        for record in reader:
            if (len(rows) >= MAX_ROWS or None in record
                    or any(value is None for value in record.values())):
                raise ValueError('invalid profile CSV row')
            rows.append(record)
    except (csv.Error, UnicodeError) as exc:
        raise ValueError('malformed profile CSV') from exc
    if not rows:
        raise ValueError('empty profile catalog')
    return rows


def _selected_variant_in_profile(t100_csv, t160_csv, t161_csv, variant_id, profile_identifier):
    """Check only static T100/T160/T161 relationships, not VIN/profile truth."""
    if (not isinstance(profile_identifier, str) or not profile_identifier.strip()
            or len(profile_identifier) > 128 or '\n' in profile_identifier
            or '\r' in profile_identifier):
        raise ValueError('invalid selected profile identifier')

    variants = set()
    for row in _bounded_fk_rows(t100_csv, {'id', 'identifier', 'fkT101_Ecu'}):
        variant = _positive_id(row['id'])
        ecu_type = _positive_id(row['fkT101_Ecu'])
        if (variant is None or variant == 0 or ecu_type is None or ecu_type == 0
                or not row['identifier'].strip() or variant in variants):
            raise ValueError('invalid or duplicate T100 variant row')
        variants.add(variant)

    profile_ids = set()
    profile_names = set()
    selected_profile_id = None
    for row in _bounded_fk_rows(t161_csv, {'id', 'identifier'}):
        identifier = row['identifier']
        profile_id = _positive_id(row['id'])
        if (profile_id is None or profile_id == 0 or not identifier.strip()
                or profile_id in profile_ids or identifier in profile_names):
            raise ValueError('invalid or duplicate T161 profile row')
        profile_ids.add(profile_id)
        profile_names.add(identifier)
        if identifier == profile_identifier:
            selected_profile_id = profile_id

    default_pairs = set()
    for row in _bounded_fk_rows(t160_csv, {'fkT161_Profile', 'fkT100_EcuVariant'}):
        profile_id = _positive_id(row['fkT161_Profile'])
        default_variant = _positive_id(row['fkT100_EcuVariant'])
        if (profile_id is None or profile_id == 0 or default_variant is None
                or default_variant == 0 or (profile_id, default_variant) in default_pairs):
            raise ValueError('invalid or duplicate T160 default-variant relation')
        default_pairs.add((profile_id, default_variant))

    return (variant_id in variants and selected_profile_id is not None
            and (selected_profile_id, variant_id) in default_pairs)

def audit_sources(xml_bytes, csv_bytes, service_definition_bytes=None,
                  protocol_catalog_bytes=None, service_ecu_variant_map_bytes=None,
                  selected_ecu_variant_id=None, t100_catalog_bytes=None,
                  t160_catalog_bytes=None, t161_catalog_bytes=None,
                  selected_profile_identifier=None):
    content, nodes = _parse_xml(xml_bytes)
    service_ids, metadata_complete_ids, protocol_complete_ids, protocol_keys_by_service_id, rows, invalid_rows, empty_metadata = _parse_catalog(csv_bytes)
    protocol_catalog_ids = (_parse_protocol_catalog(protocol_catalog_bytes)
                            if protocol_catalog_bytes is not None else None)
    if ((service_ecu_variant_map_bytes is None) != (selected_ecu_variant_id is None)):
        raise ValueError('T110 input and selected ECU variant ID must be supplied together')
    t110_pairs = None
    selected_variant = None
    if service_ecu_variant_map_bytes is not None:
        if not isinstance(selected_ecu_variant_id, str):
            raise ValueError('selected ECU variant must be a canonical decimal string')
        selected_variant = _positive_id(selected_ecu_variant_id)
        if selected_variant is None or selected_variant == 0:
            raise ValueError('invalid selected ECU variant ID')
        t110_pairs = _parse_service_ecu_variant_map(service_ecu_variant_map_bytes)
    profile_inputs = (t100_catalog_bytes, t160_catalog_bytes,
                      t161_catalog_bytes, selected_profile_identifier)
    if any(item is not None for item in profile_inputs):
        if (not all(item is not None for item in profile_inputs)
                or t110_pairs is None or selected_variant is None):
            raise ValueError('T100/T160/T161/profile selector require T110 and each other')
        static_variant_profile_match = _selected_variant_in_profile(
            t100_catalog_bytes, t160_catalog_bytes, t161_catalog_bytes,
            selected_variant, selected_profile_identifier)
    else:
        static_variant_profile_match = False
    definition_id, definition_content_present = (None, False)
    if service_definition_bytes is not None:
        definition_id, definition_content_present = _parse_service_definition(service_definition_bytes)
    readers = {n.attrib['nodeid']: n for n in nodes
               if n.attrib.get('class', '').rsplit('.', 1)[-1] == 'ReadVinComponent'}
    # Original XML property-handler setters can replace a literal ServiceId.
    overrides = set()
    identifier_setters = set()
    for handler in content.findall('./handlers/propertyhandler'):
        for setter in handler.findall('./set'):
            target = setter.attrib.get('node')
            if target not in readers or 'disabled' in setter.attrib:
                continue
            if setter.attrib.get('property') == 'ServiceId':
                overrides.add(target)
            if setter.attrib.get('property') == 'Identifier':
                identifier_setters.add(target)

    counters = {
        'readvin_nodes': len(readers),
        'readvin_nodes_with_serviceid_property': 0,
        'readvin_nodes_with_unique_direct_int_literal': 0,
        'readvin_nodes_with_missing_or_nonliteral_serviceid': 0,
        'readvin_nodes_with_duplicate_serviceid_properties': 0,
        'readvin_nodes_with_enabled_serviceid_setter': len(overrides),
        'readvin_nodes_with_enabled_identifier_setter': len(identifier_setters),
        'readvin_nodes_with_identifier_property': 0,
        'catalog_rows': rows,
        'catalog_invalid_id_rows': invalid_rows,
        'catalog_rows_with_empty_service_or_mode': empty_metadata,
        'catalog_unique_numeric_ids': len(service_ids),
        'catalog_duplicate_numeric_id_rows': sum(n - 1 for n in service_ids.values()),
        'literal_ids_with_unique_catalog_row_no_declared_override': 0,
        'literal_ids_with_unique_catalog_row_and_nonempty_service_mode': 0,
        'literal_ids_with_unique_catalog_row_but_empty_service_or_mode': 0,
        'literal_ids_without_catalog_row': 0,
        'literal_ids_with_duplicate_catalog_rows': 0,
        'literal_ids_with_declared_override': 0,
    }
    definition_qualified_matches = 0
    protocol_qualified_matches = 0
    variant_qualified_matches = 0
    for node_id, node in readers.items():
        props = node.findall('./property')
        service_props = [p for p in props if p.attrib.get('name') == 'ServiceId']
        counters['readvin_nodes_with_identifier_property'] += int(any(
            p.attrib.get('name') == 'Identifier' for p in props))
        counters['readvin_nodes_with_serviceid_property'] += int(bool(service_props))
        if len(service_props) > 1:
            counters['readvin_nodes_with_duplicate_serviceid_properties'] += 1
            continue
        value = (_positive_id(service_props[0].attrib.get('value'))
                 if len(service_props) == 1 and service_props[0].attrib.get('class') == 'Int'
                 else None)
        if value is None:
            counters['readvin_nodes_with_missing_or_nonliteral_serviceid'] += 1
            continue
        counters['readvin_nodes_with_unique_direct_int_literal'] += 1
        count = service_ids.get(value, 0)
        if count == 0:
            counters['literal_ids_without_catalog_row'] += 1
        elif count > 1:
            counters['literal_ids_with_duplicate_catalog_rows'] += 1
        elif node_id in overrides:
            counters['literal_ids_with_declared_override'] += 1
        else:
            counters['literal_ids_with_unique_catalog_row_no_declared_override'] += 1
            if metadata_complete_ids.get(value, 0) == 1:
                counters['literal_ids_with_unique_catalog_row_and_nonempty_service_mode'] += 1
                if (definition_content_present and definition_id == value and
                        protocol_complete_ids.get(value, 0) == 1):
                    definition_qualified_matches += 1
                    if (protocol_catalog_ids is not None and
                            protocol_keys_by_service_id.get(value) in protocol_catalog_ids):
                        protocol_qualified_matches += 1
                        if (t110_pairs is not None and
                                (selected_variant, value) in t110_pairs):
                            variant_qualified_matches += 1
            else:
                counters['literal_ids_with_unique_catalog_row_but_empty_service_or_mode'] += 1

    return {
        'schema_version': SCHEMA,
        'classification': 'readvin_xml_to_t111_id_static_declarations_only',
        'counts': counters,
        'static_unique_catalog_candidate_present': bool(
            counters['literal_ids_with_unique_catalog_row_no_declared_override']),
        # This stronger shape gate still proves no selected GetScript or
        # protocol bytes. Do not collapse multiple ReadVin readers into one.
        'single_readvin_with_service_mode_metadata_candidate_present': bool(
            counters['readvin_nodes'] == 1 and
            counters['literal_ids_with_unique_catalog_row_and_nonempty_service_mode'] == 1),
        'service_definition_xml_supplied': service_definition_bytes is not None,
        'single_readvin_with_matching_service_definition_root_candidate_present': bool(
            len(readers) == 1 and definition_qualified_matches == 1),
        'protocol_catalog_csv_supplied': protocol_catalog_bytes is not None,
        'single_readvin_with_matching_t122_protocol_reference_candidate_present': bool(
            len(readers) == 1 and protocol_qualified_matches == 1),
        't110_service_ecu_variant_csv_supplied': service_ecu_variant_map_bytes is not None,
        'single_readvin_with_matching_t110_service_ecu_variant_candidate_present': bool(
            len(readers) == 1 and variant_qualified_matches == 1),
        'ecu_profile_catalogs_supplied': t100_catalog_bytes is not None,
        'single_readvin_with_selected_default_ecu_variant_profile_candidate_present': bool(
            len(readers) == 1 and variant_qualified_matches == 1
            and static_variant_profile_match),
        'selected_profile_is_target_vehicle_verified': False,
        'actual_ecu_variant_identity_verified': False,
        'actual_ecu_variant_service_support_verified': False,
        'actual_protocol_transport_verified': False,
        'original_service_definition_runtime_verified': False,
        'same_installation_provenance_verified': False,
        'original_getscript_runtime_selection_verified': False,
        'runtime_serviceid_or_propertyhandler_value_verified': False,
        'carcom_service_definition_or_mode_verified': False,
        'j2534_tx_or_ecu_rx_verified': False,
        'accepted_vin_verified': False,
        'xc90_v8_my2009_identified': False,
        'emulator_replay_approved': False,
    }


def _read_zip(path):
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != '.zip':
        raise ValueError('unsupported ZIP path')
    if not 30 <= path.stat().st_size <= MAX_ZIP_BYTES:
        raise ValueError('ZIP size outside bounds')
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 1:
            raise ValueError('one ZIP member required')
        item = members[0]
        if (item.is_dir() or item.flag_bits & 1 or not item.compress_size
                or item.file_size > MAX_XML_BYTES
                or item.file_size > 100 * item.compress_size
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', item.filename)):
            raise ValueError('unsafe ZIP member')
        with archive.open(item) as stream:
            data = stream.read(MAX_XML_BYTES + 1)
        if len(data) != item.file_size or len(data) > MAX_XML_BYTES:
            raise ValueError('ZIP decompression limit')
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description='Privacy-safe static ReadVin to T111 catalog cross-check')
    ap.add_argument('readvin_zip', type=Path)
    ap.add_argument('t111_csv', type=Path)
    ap.add_argument('--service-definition', type=Path, help='optional private extracted_services/<id>.xml')
    ap.add_argument('--protocol-catalog', type=Path, help='optional same-installation T122_Protocol.csv')
    ap.add_argument('--t110-catalog', type=Path, help='optional same-installation T110_Service_EcuVariant.csv')
    ap.add_argument('--ecu-variant-id', help='canonical numeric T100_EcuVariant ID to filter the T110 map')
    ap.add_argument('--t100-catalog', type=Path, help='optional private T100_EcuVariant.csv')
    ap.add_argument('--t160-catalog', type=Path, help='optional private T160_DefaultEcuVariant.csv')
    ap.add_argument('--t161-catalog', type=Path, help='optional private T161_Profile.csv')
    ap.add_argument('--profile-identifier', help='exact selected VIDA T161 profile identifier')
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    dest = a.output.resolve()
    inputs = [a.readvin_zip, a.t111_csv]
    if a.service_definition is not None:
        inputs.append(a.service_definition)
    if a.protocol_catalog is not None:
        inputs.append(a.protocol_catalog)
    if a.t110_catalog is not None:
        inputs.append(a.t110_catalog)
    for item in (a.t100_catalog, a.t160_catalog, a.t161_catalog):
        if item is not None:
            inputs.append(item)
    if (dest == repo or repo in dest.parents
            or dest in (p.resolve() for p in inputs)
            or a.output.is_symlink() or a.output.parent.is_symlink()):
        ap.error('unsafe output location')
    try:
        if (a.t111_csv.is_symlink() or not a.t111_csv.is_file()
                or a.t111_csv.stat().st_size > MAX_CSV_BYTES):
            raise ValueError('unsupported catalog file')
        definition = None
        if a.service_definition is not None:
            path = a.service_definition
            if (path.is_symlink() or not path.is_file() or path.suffix.lower() != '.xml'
                    or path.stat().st_size > MAX_SERVICE_DEFINITION_BYTES):
                raise ValueError('unsupported private service definition')
            definition = path.read_bytes()
        protocols = None
        if a.protocol_catalog is not None:
            path = a.protocol_catalog
            if (path.is_symlink() or not path.is_file() or path.suffix.lower() != '.csv'
                    or path.stat().st_size > MAX_CSV_BYTES):
                raise ValueError('unsupported private T122 protocol catalog')
            protocols = path.read_bytes()
        t110 = None
        if a.t110_catalog is not None:
            path = a.t110_catalog
            if (path.is_symlink() or not path.is_file() or path.suffix.lower() != '.csv'
                    or path.stat().st_size > MAX_CSV_BYTES):
                raise ValueError('unsupported private T110 service-to-ECU catalog')
            t110 = path.read_bytes()
        profile_catalogs = []
        for source in (a.t100_catalog, a.t160_catalog, a.t161_catalog):
            if source is None:
                profile_catalogs.append(None)
            else:
                if (source.is_symlink() or not source.is_file()
                        or source.suffix.lower() != '.csv'
                        or source.stat().st_size > MAX_CSV_BYTES):
                    raise ValueError('unsupported private ECU profile catalog')
                profile_catalogs.append(source.read_bytes())
        report = audit_sources(_read_zip(a.readvin_zip), a.t111_csv.read_bytes(),
                               definition, protocols, t110, a.ecu_variant_id,
                               *profile_catalogs, a.profile_identifier)
        with a.output.open('x', encoding='utf-8') as out:
            json.dump(report, out, ensure_ascii=False, indent=2)
            out.write('\n')
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        ap.error('private input rejected: ' + type(exc).__name__)
    print('Static candidate categories saved. No service execution or accepted VIN verified.')


if __name__ == '__main__':
    main()
