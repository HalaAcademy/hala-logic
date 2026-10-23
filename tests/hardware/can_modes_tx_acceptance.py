#!/usr/bin/env python3
"""Real B 11/29 DATA/RTR TX, physical peer ACK and GDB, no jumpers."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import shutil
import traceback
from client import Monitor,wait_monitor
from flash import flash_student
from swd import ROOT,set_mode
from gdb_checks import symbols,debug_server,run_gdb
from gdb_examples_acceptance import COMMANDS
from export import export_capture
import decode,stimulus


def main():
    directory=ROOT/'build/reports'/('can-modes-tx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True);(directory/'firmware').mkdir()
    report={'scope':'11/29 DATA/RTR TX with ACK observer; no automatic RTR data reply/arbitration/error FSM',
            'fixture':'one MCU, physical PB0/PB10 AND resolved onto real PB8, no jumpers','results':[]}
    def save():(directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        for extended,remote,suffix in [(False,False,''),(True,False,'_ext'),(False,True,'_rtr'),(True,True,'_ext_rtr')]:
            name='student_can2_tx'+suffix;elf=ROOT/'build'/f'{name}.elf'
            for ext in ('elf','bin'):shutil.copy2(elf.with_suffix('.'+ext),directory/'firmware'/f'{name}.{ext}')
            syms=symbols(elf)
            flash_student(elf,None,report_dir=directory/f'flash-{name}');wait_monitor(True)
            identifier=0x12345678 if extended else 0x123
            payload=b'' if remote else bytes([0,255,85,170,0,255,0,255])
            expected=stimulus.can(identifier,payload,extended=extended,remote=remote,dlc=8)
            # Encoder has 12 leading idle and 25 trailer bits. CRC delimiter
            # is followed by ACK, so its position from SOF is len - 36.
            ack=(len(expected)-36)*4
            peer=[0x400]*((len(expected)-12)*4)
            peer[ack:ack+4]=[0]*4
            with Monitor() as m:
                job=m.stimulus_upload(peer,64000,mask=0x400,idle=0x400,repeat=16)
                m.bridge(0x401)
                before=m.registers(syms['tx_ack_count'])[0]
                cap,samples=m.capture_stream('B',16000,16384,0x501,
                    on_start=lambda:m.stimulus_arm(job['id'],idle_ticks=11*64))
                bus=decode.can(decode.levels(samples,8),16000,1000)
                tx=decode.can(decode.levels(samples,0),16000,1000)
                state=m.stimulus_status();after=m.registers(syms['tx_ack_count'])[0]
                missing=m.registers(syms['tx_no_ack_count'])[0]
                export_capture(directory/name,cap,samples,bus,m.info(),{'peer':state})
                assert state['state']==3 and not state['underruns'],state
                assert len(bus)>=2 and len(tx)>=2,(bus,tx)
                assert all((f['id'],f['extended'],f['remote'],f['dlc'],f['data'],f['crc_ok'])==
                           (identifier,extended,remote,8,payload.hex(),True) for f in bus),bus
                assert sum(f['ack'] for f in bus)==1 and all(not f['ack'] for f in tx),(bus,tx)
                assert after-before==1 and missing>0,(before,after,missing)
                m.stimulus_stop()
            with debug_server(directory/name):
                log=run_gdb('''monitor halt
if tx_ack_count != 1 || tx_no_ack_count == 0
 echo FAIL: B ACK observation\\n
 quit 1
end
printf "PASS: GDB B ACK=%u missing=%u frames=%u\\n",tx_ack_count,tx_no_ack_count,student_frames
detach
''',elf,directory/name,'ack-oracle')
                log=run_gdb(COMMANDS,elf,directory/name,'main-isr-watch')
                assert 'Old value =' in log and 'New value =' in log,'Missing watchpoint value evidence'
            wait_monitor(True)
            with Monitor() as m:stack=json.loads(m.command('STACK'))
            assert stack['a_msp_unwritten_bytes']>=256 and stack['b_psp_unwritten_bytes']>=128,stack
            report['results'].append({'name':name,'status':'PASS','bus_frames':bus,'B_ack_count':after,
                                      'B_no_ack_count':missing,'stack':stack})
            save();print('PASS: B Classical CAN TX/ACK/GDB',name,flush=True)
        flash_student(ROOT/'build/student.elf',None,report_dir=directory/'restore-pwm')
        wait_monitor(True);report['automated_status']='PASS'
    except Exception as exc:
        report.update(automated_status='INVALID' if 'INVALID' in str(exc) else 'FAIL',error=str(exc))
        (directory/'failure.log').write_text(traceback.format_exc())
        try:set_mode(True,None,directory/'safe.log')
        except Exception:pass
        raise
    finally:
        save();print('Evidence:',directory,flush=True)


if __name__=='__main__':main()
