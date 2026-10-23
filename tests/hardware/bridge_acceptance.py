#!/usr/bin/env python3
"""Verify REAL pad-to-pad relay, no jumper: PB10 peer -> A resolver -> PB8 B RX."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import time
import traceback
from client import Monitor,wait_monitor
from flash import flash_student
from swd import ROOT,set_mode
from gdb_checks import symbols
from export import export_capture
import decode,stimulus


def main():
    directory=ROOT/'build/reports'/('bridge-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    report={'fixture':'one MCU, physical PB10 -> software pad resolver -> physical PB8; NO JUMPERS'}
    try:
        flash_student(ROOT/'build/student_uart_rx.elf',None,report_dir=directory/'flash-rx')
        wait_monitor(True)
        syms=symbols(ROOT/'build/student_uart_rx.elf')
        with Monitor() as monitor:
            before=monitor.registers(syms['rx_count'])[0]
            job=monitor.stimulus_upload(stimulus.uart(b'RELAY',pin=10),16000,
                                        mask=0x400,idle=0x400,repeat=16)
            monitor.bridge(0x400) # UART RX doesn't AND its simultaneous echo into input.
            start={}
            def launch(): start.update(monitor.stimulus_start(job['id']))
            status,samples=monitor.capture_stream('B',32000,4096,0x501,on_start=launch)
            state=monitor.stimulus_status()
            after=monitor.registers(syms['rx_count'])[0]
            decoded={str(pin):decode.uart(decode.levels(samples,pin),32000,1000) for pin in [0,8,10]}
            export_capture(directory/'relay-UART',status,samples,decoded['8'],monitor.info(),{'stimulus':state})
            edges=lambda pin:[i for i in range(1,len(samples)) if (samples[i]^samples[i-1])&(1<<pin)]
            source,dest=edges(10),edges(8)
            diffs=[b-a for a,b in zip(source,dest)]
            report.update({'capture':status,'stimulus':state,'decoded':decoded,
                           'source_edges':source,'dest_edges':dest,'skew_samples':diffs,
                           'rx_count_before':before,'rx_count_after':after})
            assert [f['value'] for f in decoded['10']]==list(b'RELAY')
            assert [f['value'] for f in decoded['8']]==list(b'RELAY')
            assert [f['value'] for f in decoded['0']]==[b^32 for b in b'RELAY']
            assert after-before==5 and state['underruns']==0
            assert len(source)==len(dest) and all(0<=d<=2 for d in diffs),diffs
            assert state['bridge_ticks']>1000
            monitor.bridge(0)
        flash_student(ROOT/'build/student.elf',None,report_dir=directory/'restore-pwm')
        wait_monitor(True)
        report['automated_status']='PASS'
        print('PASS: physical pad relay, B RX and XOR reply; skew <=2 samples at 32kS/s',flush=True)
    except Exception as exc:
        report.update(automated_status='FAIL',error=str(exc))
        (directory/'failure.log').write_text(traceback.format_exc())
        try:set_mode(True,None,directory/'safe.log')
        except Exception:pass
        raise
    finally:
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Evidence:',directory,flush=True)


if __name__=='__main__':main()
