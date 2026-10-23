#!/usr/bin/env python3
"""LIN subscriber + header-triggered publisher on physical pads without jumper."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import struct
import traceback
from client import Monitor,wait_monitor
from flash import flash_student
from swd import ROOT,set_mode
from gdb_checks import symbols,debug_server,run_gdb
from export import export_capture
import decode,stimulus


def main():
    directory=ROOT/'build/reports'/('lin-rx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    report={'scope':'LIN software subscriber ID12 and publisher ID22, 2 bytes, enhanced checksum',
            'fixture':'physical PB0/PB10 AND relay -> physical PB8, no jumper','results':[]}
    syms=symbols(ROOT/'build/student_lin_rx.elf')
    def state(m):
        result={s:m.registers(syms[s])[0] for s in ['rx_count','rx_errors','pid_errors',
                'checksum_errors','publisher_count','rx_id','rx_pid','student_max_lateness_ticks']}
        address=syms['rx_data']; word=m.registers(address&~3)[0]
        result['data']=((word>>((address&3)*8))&65535).to_bytes(2,'little').hex()
        return result
    def save():(directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        flash_student(ROOT/'build/student_lin_rx.elf',None,report_dir=directory/'flash-lin-rx')
        wait_monitor(True)
        with Monitor() as monitor:
            cases=[('subscriber',0x12,b'\x34\x56',{}),
                   ('bad-checksum',0x12,b'\x34\x56',{'corrupt_checksum':True}),
                   ('bad-PID',0x12,b'\x34\x56',{'corrupt_pid':True}),
                   ('publisher',0x22,b'',{'header_only':True}),
                   ('recovery',0x12,b'\x00\xff',{})]
            for name,identifier,payload,options in cases:
                levels=stimulus.lin(identifier,payload,**options)
                job=monitor.stimulus_upload(levels,16000,mask=0x400,idle=0x400,repeat=16)
                monitor.bridge(0x401)
                before=state(monitor)
                status,samples=monitor.capture_stream('B',32000,8192,0x501,
                    on_start=lambda:monitor.stimulus_start(job['id']))
                after=state(monitor);tx=monitor.stimulus_status()
                frames=decode.lin(decode.levels(samples,8),32000,1000,data_length=2)
                export_capture(directory/name,status,samples,frames,monitor.info(),
                               {'before':before,'after':after,'stimulus':tx})
                result={'name':name,'before':before,'after':after,'bus_frames':frames,'tx':tx}
                (directory/(name+'-observed.json')).write_text(json.dumps(result,indent=2)+'\n')
                assert tx['state']==3 and not tx['underruns'],result
                assert len(frames)==1,result
                if name=='bad-checksum':
                    assert not frames[0]['checksum_ok'],result
                    assert after['checksum_errors']==before['checksum_errors']+1,result
                    assert after['rx_count']==before['rx_count'],result
                elif name=='bad-PID':
                    assert not frames[0]['parity_ok'],result
                    assert after['pid_errors']==before['pid_errors']+1,result
                    assert after['rx_count']==before['rx_count'],result
                elif name=='publisher':
                    assert frames[0]['id']==0x22 and frames[0]['data']=='3456',result
                    assert frames[0]['checksum_ok'] and frames[0]['parity_ok'],result
                    assert after['publisher_count']==before['publisher_count']+1,result
                    assert after['rx_count']==before['rx_count'],result
                else:
                    assert frames[0]['checksum_ok'] and frames[0]['parity_ok'],result
                    assert after['rx_count']==before['rx_count']+1,result
                    assert after['data']==payload.hex() and after['rx_id']==identifier,result
                result['status']='PASS';report['results'].append(result);save()
                print('PASS: LIN software',name,flush=True)
                monitor.bridge(0)
        with debug_server(directory/'gdb'):
            run_gdb('''monitor halt
if rx_count != 2 || publisher_count != 1 || pid_errors != 1 || checksum_errors != 1
 echo FAIL: LIN B app variables incorrect\\n
 quit 1
end
printf "PASS: GDB LIN B subscriber=%u publisher=%u pid_errors=%u checksum_errors=%u\\n", rx_count, publisher_count, pid_errors, checksum_errors
hbreak TIM4_IRQHandler
continue
printf "PASS: B software LIN TIM4 ISR, IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
''',ROOT/'build/student_lin_rx.elf',directory/'gdb','lin-rx')
        flash_student(ROOT/'build/student.elf',None,report_dir=directory/'restore-pwm')
        wait_monitor(True);report['automated_status']='PASS'
    except Exception as exc:
        report.update(automated_status='FAIL',error=str(exc))
        (directory/'failure.log').write_text(traceback.format_exc())
        try:set_mode(True,None,directory/'safe.log')
        except Exception:pass
        raise
    finally:
        save(); print('Evidence:',directory,flush=True)


if __name__=='__main__':main()
