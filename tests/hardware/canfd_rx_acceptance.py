#!/usr/bin/env python3
"""Hardware ISO FD 11/29 RX: all 16 DLC, BRS off/on, CRC17/21 and faults."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import struct
import traceback
import shutil
from client import Monitor,wait_monitor
from flash import flash_student
from swd import ROOT,set_mode
from gdb_checks import symbols,debug_server,run_gdb
from gdb_examples_acceptance import COMMANDS
from export import export_capture
import canfd


def main():
    directory=ROOT/'build/reports'/('canfd-rx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    (directory/'firmware').mkdir()
    for image in ('monitor','student_canfd_rx'):
        for suffix in ('elf','bin'):
            shutil.copy2(ROOT/'build'/f'{image}.{suffix}',directory/'firmware'/f'{image}.{suffix}')
    report={'scope':'ISO FD 11/29 teaching RX/ACK, 1k nominal, 2k BRS; not full error-confinement',
            'fixture':'physical PB0/PB10 AND relay -> physical PB8, NO JUMPERS','results':[]}
    syms=symbols(ROOT/'build/student_canfd_rx.elf')
    def state(m):
        result={s:m.registers(syms[s])[0] for s in ['rx_count','rx_errors','rx_crc_errors',
                'rx_stuff_errors','rx_form_errors','rx_id','rx_extended','rx_length','rx_brs','rx_esi',
                'ack_count','student_max_lateness_ticks','student_max_irq_gap_us']}
        data=b''
        for off in (0,32):data+=struct.pack('<8I',*m.registers(syms['rx_data']+off,8))
        result['data']=data.hex()
        return result
    def save():(directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        flash_student(ROOT/'build/student_canfd_rx.elf',None,report_dir=directory/'flash-canfd-rx')
        wait_monitor(True)
        with Monitor() as monitor:
            cases=[]
            for extended in (False,True):
                prefix='ext-' if extended else ''
                for brs in (False,True):
                    for length in canfd.LENGTHS:
                        data=bytes(((i*37+length)&255) for i in range(length))
                        cases.append((f'{prefix}brs{int(brs)}-len{length}',data,{'brs':brs,'extended':extended}))
                cases += [(prefix+'bad-crc',b'\xff'*8,{'corrupt_crc':True,'extended':extended}),
                          (prefix+'bad-count',b'\xff'*8,{'corrupt_count':True,'extended':extended}),
                          (prefix+'recovery',bytes(range(64)),{'brs':True,'esi':True,'extended':extended})]
            for name,data,options in cases:
                identifier=0x1fffffff if options['extended'] and len(data)==64 else 0x12345678 if options['extended'] else 0x5aa
                levels,expected=canfd.frame(identifier,data,**options)
                job=monitor.stimulus_upload(levels,64000,mask=0x400,idle=0x400,repeat=16)
                monitor.bridge(0x401);before=state(monitor)
                status,samples=monitor.capture_stream('B',16000,16384,0x501,
                    on_start=lambda:monitor.stimulus_start(job['id']))
                after=state(monitor);tx=monitor.stimulus_status()
                frames=canfd.decode([(v>>8)&1 for v in samples],16000)
                peer=canfd.decode([(v>>10)&1 for v in samples],16000)
                export_capture(directory/name,status,samples,frames,monitor.info(),
                               {'before':before,'after':after,'stimulus':tx,'expected':expected})
                result={'name':name,'expected':expected,'before':before,'after':after,
                        'bus_frames':frames,'peer_frames':peer,'tx':tx}
                (directory/(name+'-observed.json')).write_text(json.dumps(result,indent=2)+'\n')
                assert tx['state']==3 and not tx['underruns'],result
                assert len(frames)==1 and len(peer)==1,result
                frame=frames[0]
                assert frame['data']==data.hex() and frame['format_ok'],result
                assert frame['id']==identifier and frame['extended']==options['extended'],result
                if options.get('corrupt_crc'):
                    assert not frame['crc_ok'] and not frame['ack'],result
                    assert after['rx_crc_errors']==before['rx_crc_errors']+1,result
                    assert after['rx_count']==before['rx_count'],result
                elif options.get('corrupt_count'):
                    assert not frame['stuff_count_ok'] and not frame['ack'],result
                    assert after['rx_stuff_errors']==before['rx_stuff_errors']+1,result
                    assert after['rx_count']==before['rx_count'],result
                else:
                    assert frame['crc_ok'] and frame['stuff_count_ok'] and frame['ack'],result
                    assert not peer[0]['ack'],result
                    assert after['rx_count']==before['rx_count']+1,result
                    assert after['rx_length']==len(data) and after['rx_id']==identifier,result
                    assert after['rx_extended']==int(options['extended']),result
                    assert after['data'][:len(data)*2]==data.hex(),result
                    assert after['rx_brs']==int(expected['brs']) and after['rx_esi']==int(expected['esi'])
                    assert after['rx_errors']==before['rx_errors'],result
                result['status']='PASS';report['results'].append(result);save()
                print('PASS: ISO FD real-pad software RX/ACK',name,flush=True)
                monitor.bridge(0)
        with debug_server(directory/'gdb'):
            run_gdb('''monitor halt
if rx_count != 66 || ack_count != 66 || rx_crc_errors != 2 || rx_stuff_errors != 2
 echo FAIL: CAN FD B app variables incorrect\\n
 quit 1
end
printf "PASS: GDB ISO FD B RX=%u ACK=%u CRC-errors=%u count-errors=%u length=%u BRS=%u ESI=%u\\n", rx_count, ack_count, rx_crc_errors, rx_stuff_errors, rx_length, rx_brs, rx_esi
hbreak TIM4_IRQHandler
continue
printf "PASS: FD software B timer ISR IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
''',ROOT/'build/student_canfd_rx.elf',directory/'gdb','canfd-rx')
            log=run_gdb(COMMANDS,ROOT/'build/student_canfd_rx.elf',directory/'gdb','main-isr-watch')
            assert 'Old value =' in log and 'New value =' in log,'Missing GDB watchpoint value evidence'
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
