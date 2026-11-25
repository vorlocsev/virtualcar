"""Read-only catalog index. No transport, no synthesized CAN IDs or ECU replies."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from collections import defaultdict

PROFILE = (163120, '0b00c8af83f1a29b', 'XC90 2009 B8444S ')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def route_key(r):
    require(r['protocol'] in ('D2', 'GGD'), 'unsupported protocol')
    require(type(r['bus']) is int and r['bus'] in (0,1), 'unresolved bus')
    require(isinstance(r['commAddress'], str) and re.fullmatch(r'[0-9a-fA-F]{2}',r['commAddress']), 'unresolved address')
    return (r['protocol'], r['bus'], r['commAddress'].upper())

def build(d):
    require(d['schema']=='vc045-catalog-topology-v1', 'schema mismatch')
    require(d['catalog_only'] is True and all(d[k] is False for k in ('runtime_verified','topology_verified','replay_approved')), 'unexpected evidence status')
    p=d['selected_profile']
    require(p and (p['id'],p['identifier'],p['title'])==PROFILE, 'wrong profile')
    require(sum(x==p for x in d['candidate_profiles'])==1, 'profile not uniquely listed')
    require(d['cem_candidate']=={'id':2160,'identifier':'31296075 AA'}, 'CEM identity mismatch')
    variants=d['expected_variants']; require(bool(variants),'empty catalog')
    index={}; ids=set(); configs=set(); collisions=defaultdict(list)
    for v in variants:
        vid=v['variant_id']; require(type(vid) is int and vid not in ids,'duplicate variant'); ids.add(vid)
        require(v['variant_resolved'] is True and v['ecu_resolved'] is True,'unresolved variant or ECU')
        require(v['presence_verified'] is False and v['response_verified'] is False,'unexpected runtime claim')
        require(bool(v['routes']), 'missing route')
        for r in v['routes']:
            key=route_key(r)
            require(key not in index,'ambiguous protocol/bus/address')
            cid=r['config_id']; require(type(cid) is int and cid==r['resolved_config_id'] and cid not in configs,'unresolved or duplicate config'); configs.add(cid)
            require(r['protocol_id']=={'D2':5,'GGD':7}[key[0]],'protocol id mismatch')
            require(r['bus_id']=={0:3,1:1}[key[1]],'bus id mismatch')
            require(r['busRate'] in (None,'','500000'),'unreviewed bus rate')
            for k in ('canIdTX','canIdRX'):
                require(r[k] in (None,'000'),'unreviewed CAN ID')
            item={'key':list(key),'variant_id':vid,'variant_identifier':v['variant_identifier'],'ecu_id':v['ecu_id'],'ecu_identifier':v['ecu_identifier'],'ecu_name':v['ecu_name'],'source_route':dict(r),'runtime_can_ids_resolved':False,'runtime_bus_rate_verified':False,'presence_verified':False,'response_verified':False}
            index[key]=item; collisions[key[1:]].append(list(key))
    require(2160 in ids and 529 in ids,'missing CEM variants')
    require(index.get(('D2',1,'50'),{}).get('variant_id')==2160 and index.get(('D2',0,'40'),{}).get('variant_id')==2160 and index.get(('GGD',1,'50'),{}).get('variant_id')==529,'CEM routes mismatch')
    return {'schema':'vc046-route-catalog-v1','selected_profile':dict(p),'routes':list(index.values()),'address_collisions':[{'bus':k[0],'address':k[1],'keys':v} for k,v in collisions.items() if len(v)>1],'catalog_only':True,'complete_network_verified':False,'runtime_verified':False,'replay_approved':False}

def lookup(catalog,protocol,bus,address):
    key=route_key({'protocol':protocol,'bus':bus,'commAddress':address})
    matches=[r for r in catalog['routes'] if tuple(r['key'])==key]
    require(len(matches)==1,'missing or ambiguous route')
    return matches[0]
