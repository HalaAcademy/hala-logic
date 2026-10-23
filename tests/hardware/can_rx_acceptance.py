#!/usr/bin/env python3
"""Classical CAN software RX/ACK on REAL pads through generic no-wire resolver."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import struct
import time
import traceback
from client import Monitor,wait_monitor
from flash import flash_student
from swd import ROOT,set_mode
from gdb_checks import symbols,debug_server,run_gdb
from gdb_examples_acceptance import COMMANDS
from export import export_capture
import decode,stimulus


def main():
    directory=ROOT/'build/reports'/('can-rx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    report={'scope':'software CAN 11/29 data/remote RX + CRC/stuffing + ACK; no arbitration/error-confinement/automatic RTR response claim',
            'fixture':'physical PB0 B_TX and PB10 peer resolved into physical PB8; NO JUMPERS',
            'results':[]}
    syms=symbols(ROOT/'build/student_can_rx.elf')
    def state(m):
        names=['rx_count','rx_errors','rx_crc_errors','rx_stuff_errors','rx_form_errors',
               'rx_id','rx_dlc','rx_extended','rx_remote','ack_count','student_max_lateness_ticks']
        result={s:m.registers(syms[s])[0] for s in names}
        result['data']=struct.pack('<II',*m.registers(syms['rx_data'],2)).hex()
        return result
    def save(): (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        flash_student(ROOT/'build/student_can_rx.elf',None,report_dir=directory/'flash-can-rx')
        wait_monitor(True)
        with Monitor() as monitor:
            cases=[('base-DEAD',0x123,b'\xde\xad',False,False,False,2),
                   ('empty-ID0',0,b'',False,False,False,0),
                   ('max-ID-data',0x7ff,bytes([0,255,85,170,0,0,255,255]),False,False,False,8)]
            for extended in (False,True):
                for remote in (False,True):
                    for dlc in range(9):
                        identifier=(0x1fffffff if dlc==8 else 0x12345678 if dlc else 0) if extended else 0x321
                        payload=b'' if remote else bytes([0,255,85,170,0,255,0,255][:dlc])
                        cases.append((f'{"ext" if extended else "base"}-{"RTR" if remote else "data"}-dlc{dlc}',
                                      identifier,payload,False,extended,remote,dlc))
            cases.extend([('bad-CRC',0x123,b'\xde\xad',True,False,False,2),
                          ('ext-bad-CRC',0x12345678,b'\xff'*8,True,True,False,8),
                          ('recovery',0x456,b'\x12\x34',False,False,False,2)])
            expected_count=sum(not c[3] for c in cases)
            for name,identifier,payload,bad_crc,extended,remote,dlc in cases:
                levels=stimulus.can(identifier,payload,corrupt_crc=bad_crc,extended=extended,remote=remote,dlc=dlc)
                job=monitor.stimulus_upload(levels,16000,mask=0x400,idle=0x400,repeat=16)
                monitor.bridge(0x401)
                before=state(monitor)
                status,samples=monitor.capture_stream('B',32000,8192,0x501,
                    on_start=lambda:monitor.stimulus_start(job['id']))
                after=state(monitor)
                tx=monitor.stimulus_status()
                frames=decode.can(decode.levels(samples,8),32000,1000)
                peer=decode.can(decode.levels(samples,10),32000,1000)
                export_capture(directory/name,status,samples,frames,monitor.info(),
                               {'before':before,'after':after,'stimulus':tx})
                result={'name':name,'before':before,'after':after,'bus_frames':frames,'peer_frames':peer,'tx':tx}
                (directory/(name+'-observed.json')).write_text(json.dumps(result,indent=2)+'\n')
                assert tx['state']==3 and not tx['underruns'],tx
                assert len(frames)==1 and len(peer)==1,result
                frame=frames[0]
                assert frame['id']==identifier and frame['data']==payload.hex(),result
                assert frame['extended']==extended and frame['remote']==remote and frame['dlc']==dlc,result
                if bad_crc:
                    assert not frame['crc_ok'] and not frame['ack'],result
                    assert after['rx_count']==before['rx_count'],result
                    assert after['rx_crc_errors']==before['rx_crc_errors']+1,result
                    assert after['ack_count']==before['ack_count'],result
                else:
                    assert frame['crc_ok'] and frame['ack'],result
                    assert not peer[0]['ack'],result # ACK originates in physical B_TX, not host encoding
                    assert after['rx_count']==before['rx_count']+1,result
                    assert after['rx_id']==identifier and after['rx_dlc']==dlc,result
                    assert after['rx_extended']==int(extended) and after['rx_remote']==int(remote),result
                    assert after['data'][:len(payload)*2]==payload.hex(),result
                    assert after['ack_count']==before['ack_count']+1,result
                    assert after['rx_errors']==before['rx_errors'],result
                result['status']='PASS'; report['results'].append(result); save()
                print('PASS: CAN software RX/ACK',name,flush=True)
                monitor.bridge(0)
        with debug_server(directory/'gdb'):
            run_gdb('''monitor halt
if rx_count != @GOOD@ || ack_count != @GOOD@ || rx_crc_errors != 2
 echo FAIL: CAN B app variables incorrect\\n
 quit 1
end
printf "PASS: GDB CAN B rx_count=%u ack_count=%u crc_errors=%u ID=%#x\\n", rx_count, ack_count, rx_crc_errors, rx_id
hbreak TIM4_IRQHandler
continue
printf "PASS: B software CAN TIM4 ISR, IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
'''.replace('@GOOD@',str(expected_count)),ROOT/'build/student_can_rx.elf',directory/'gdb','can-rx')
            log=run_gdb(COMMANDS,ROOT/'build/student_can_rx.elf',directory/'gdb','main-isr-watch')
            assert 'Old value =' in log and 'New value =' in log,'Missing watchpoint old/new values'
        flash_student(ROOT/'build/student.elf',None,report_dir=directory/'restore-pwm')
        wait_monitor(True)
        report['automated_status']='PASS'
    except Exception as exc:
        report.update(automated_status='FAIL',error=str(exc))
        (directory/'failure.log').write_text(traceback.format_exc())
        try:set_mode(True,None,directory/'safe.log')
        except Exception:pass
        raise
    finally:
        save();print('Evidence:',directory,flush=True)


if __name__=='__main__':main()
