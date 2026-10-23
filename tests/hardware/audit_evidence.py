#!/usr/bin/env python3
"""Read-only evidence audit with NO production encoder/decoder/client imports.

Re-reads raw GPIO bytes, integrity/counts, pad resolver truth table, UART
literal payloads, ACK pulse widths/provenance, flash preservation, and actual
GDB breakpoint/watchpoint output. Does not certify whole bus specifications.
"""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
GROUPS=['acceptance','no-wire','stream','bridge','can-rx','can-modes-tx','lin-rx','canfd-rx','flexray-rx','advanced-tx','gdb-examples']


def uart_reference(samples,hz,pin):
    # Independent timing reconstruction; no decode.py/stimulus.py code called.
    data=[(v>>pin)&1 for v in samples];spb=hz/1000;result=[];i=1;idle=0;sync=False
    while i+10*spb<len(data):
        idle=idle+1 if data[i-1] else 0
        if data[i-1] and not data[i]:
            if idle>=10*spb:sync=True
            if sync:
                centres=[int(i+(n+.5)*spb) for n in range(10)]
                frame=[data[n] for n in centres]
                if frame[0]==0 and frame[-1]==1:
                    result.append(sum(frame[n+1]<<n for n in range(8)))
                    i=int(i+9.75*spb);idle=0;continue
                sync=False
        i+=1
    return result


def complete_low_pulses(samples,pin):
    start=None;values=[]
    for i in range(1,len(samples)):
        before=(samples[i-1]>>pin)&1;now=(samples[i]>>pin)&1
        if before and not now:start=i
        elif not before and now and start is not None:
            values.append((start,i));start=None
    return values


def audit(directory):
    report=json.loads((directory/'report.json').read_text())
    if report.get('automated_status')!='PASS':
        raise AssertionError(f'Latest run did not PASS: {directory}')
    result={'directory':str(directory),'captures':0,'samples':0,'resolver_samples_checked':0,
            'GDB_logs':0,'flash_records':0}
    for path in directory.glob('*.json'):
        meta=json.loads(path.read_text())
        if not isinstance(meta,dict) or 'capture' not in meta or not path.with_suffix('.bin').exists():continue
        raw=path.with_suffix('.bin').read_bytes();cap=meta['capture'];n=cap['count']
        assert len(raw)==2*n,(path,'sample length')
        assert meta.get('raw_sha256')==hashlib.sha256(raw).hexdigest(),(path,'missing/mismatched raw hash')
        assert cap['state']==2 and not cap.get('lost'),(path,'invalid acquisition quality')
        samples=struct.unpack('<'+'H'*n,raw);hz=72000000/cap['ticks']
        result['captures']+=1;result['samples']+=n
        regs=meta.get('registers_after_capture') or {}
        peer=regs.get('stimulus') or regs.get('peer') or {}
        mask=peer.get('bridge_mask',0)
        if mask:
            # Edge-armed jobs start the relay after acquisition has begun.
            # Do not assert a physical pad contract before TIM1 is active.
            cycles=(peer['t0_cycles']-cap['t0_cycles'])&0xffffffff
            if cycles&0x80000000:cycles-=1<<32
            first=max(4,math.ceil(cycles*hz/72000000)+4)
            assert first<n,(path,'no captured active resolver window')
            result.setdefault('resolver_active_windows',[]).append({'file':path.name,'first_sample':first,'stop_sample':n})
            for i in range(first,n):
                current=samples[i]&mask
                if all(samples[j]&mask==current for j in range(i-4,i)):
                    assert bool(samples[i]&256)==(current==mask),(path,'pad resolver truth',i)
                    result['resolver_samples_checked']+=1
        if path.stem=='uart-rx-HELLO':
            assert uart_reference(samples,hz,8)==list(b'HELLO')
            assert uart_reference(samples,hz,0)==list(b'hello')
        if path.stem=='uart-rx-recovery':
            assert uart_reference(samples,hz,8)==[0,255,85,170]
            assert uart_reference(samples,hz,0)==[32,223,117,138]
        if directory.name.startswith(('can-rx-','canfd-rx-')):
            observation=json.loads(path.with_name(path.stem+'-observed.json').read_text())
            delta=observation['after']['ack_count']-observation['before']['ack_count']
            pulses=complete_low_pulses(samples,0)
            assert len(pulses)==delta,(path,'physical B ACK count',pulses,delta)
            assert all(abs((b-a)/hz-.001)<=2/hz for a,b in pulses),(path,'ACK width')
            for a,b in pulses:
                assert all(samples[i]&1024 for i in range(a,b)),(path,'ACK did not originate only in B')
        if path.stem.startswith('canfd-B-TX-ACK') or directory.name.startswith('can-modes-tx-'):
            pulses=complete_low_pulses(samples,10)
            assert len(pulses)==1,(path,'peer ACK pulse count')
            a,b=pulses[0]
            assert abs((b-a)/hz-.001)<=2/hz,(path,'peer ACK width')
    for log in directory.rglob('*.log'):
        text=log.read_text(errors='replace')
        if log.name in ('main-isr-watch.log','core.log'):
            assert 'Old value =' in text and 'New value =' in text,log
            assert 'PASS: B main breakpoint' in text and 'FAIL:' not in text,log
            if log.name=='main-isr-watch.log':
                assert 'PASS: B stepi' in text and 'PASS: B TIM4 ISR' in text,log
            result['GDB_logs']+=1
        elif 'PASS: GDB' in text or 'PASS: B RX variables' in text or 'PASS: ordinary B RX variables' in text:
            assert 'FAIL:' not in text,log
            result['GDB_logs']+=1
    for path in directory.rglob('report.json'):
        d=json.loads(path.read_text())
        if 'resident_preserved' in d:
            assert d['resident_preserved'] and d['a_bytes_compared']==24576,path
            assert d['a_sha256_before']==d['a_sha256_after'],path
            result['flash_records']+=1
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directories',nargs='*',type=Path)
    args=parser.parse_args()
    directories=args.directories
    if not directories:
        directories=[]
        for name in GROUPS:
            found=sorted((ROOT/'build/reports').glob(name+'-20*/report.json'))
            if not found:raise RuntimeError(f'Missing evidence group {name}')
            directories.append(found[-1].parent) # latest, never silently pick an older PASS
    report={'scope':'raw integrity, GPIO truth/ACK/UART, GDB execution and A preservation; not full standard conformance',
            'results':[]}
    output=ROOT/'build/reports'/('audit-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True)
    try:
        for directory in directories:
            checked=audit(directory);report['results'].append(checked)
            print('AUDIT PASS:',directory.name,{k:v for k,v in checked.items() if k!='resolver_active_windows'},flush=True)
        report['status']='PASS_IMPLEMENTED_EVIDENCE_SCOPE'
    except Exception as exc:
        report.update(status='FAIL',error=str(exc));raise
    finally:
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Independent data audit:',output,flush=True)


if __name__=='__main__':main()
