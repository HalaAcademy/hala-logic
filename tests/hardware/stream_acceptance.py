#!/usr/bin/env python3
"""Long real GPIO DMA capture/pattern evidence; intentional loss must be detected."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import datetime
import json
import random
import time
import traceback
from client import Monitor, wait_monitor
from export import export_capture
from swd import ROOT
from gdb_checks import debug_server, run_gdb


def main():
    directory=ROOT/'build/reports'/('stream-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    report={'fixture':'one MCU, real GPIO, no wires','results':[]}
    def save(): (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def passed(name,evidence):
        report['results'].append({'name':name,'status':'PASS','evidence':evidence})
        save(); print('PASS:',name,flush=True)
    try:
        info=wait_monitor(True)
        with Monitor() as monitor:
            rng=random.Random(20261023)
            levels=[0x500]*12+[rng.choice([0,0x100,0x400,0x500]) for _ in range(1000)]+[0x500]*12
            job=monitor.stimulus_upload(levels,1000,mask=0x500,idle=0x500)
            start={}
            def launch(): start.update(monitor.stimulus_start(job['id']))
            status,samples=monitor.capture_stream('B',16000,18432,0x501,on_start=launch)
            tx=monitor.stimulus_status()
            export_capture(directory/'two-channel-long',status,samples,info=info,
                           registers={'tx':tx,'stimulus_start':start})
            (directory/'expected-levels.json').write_text(json.dumps(levels)+'\n')
            assert tx['state']==3 and tx['underruns']==0,tx
            assert not status['lost'] and status['produced']==18432
            delta=(start['t0_cycles']-status['t0_cycles']) & 0xffffffff
            mismatches=[]
            for i,level in enumerate(levels[:-1]):
                index=int((delta+(i+1.5)*start['ticks'])/status['ticks'])-1
                if not 0 <= index < len(samples) or samples[index]&0x500 != level:
                    mismatches.append([i,index,level,samples[index]&0x500 if 0<=index<len(samples) else None])
            assert not mismatches,mismatches[:20]
            passed('1024-symbol two-pad DMA TX vs 18432-sample continuous GPIO capture',
                   {'status':status,'tx':tx,'symbols_checked':len(levels)-1,'seed':20261023})
            # Reuse the same buffers over many wraps and higher qualified rates.
            for hz in (10000,32000,50000):
                state,values=monitor.capture_stream('B',hz,8192,1)
                assert len(values)==8192 and state['lost']==0
                export_capture(directory/f'pwm-stream-{hz}',state,values,info=info)
                passed(f'lossless host drain at {hz} samples/s',state)
            monitor.command('CAPSTREAM B 50000 8192 1')
            time.sleep(.12) # intentionally never acknowledge a DMA half
            lost=monitor.capture_status()
            assert lost['state']==4 and lost['lost']>0,lost
            try: monitor.command('BLOCK 1 0 256')
            except RuntimeError: pass
            else: raise AssertionError('read succeeded after DMA overrun')
            passed('slow host overrun invalidates capture instead of silently joining blocks',lost)
            monitor.command('STOP')
        # Force output refill starvation while timer/DMA keep running.
        with debug_server(directory/'gdb'):
            with Monitor() as monitor:
                levels=[0x100 if i&1 else 0 for i in range(2000)]+[0x100]
                job=monitor.stimulus_upload(levels,1000)
                monitor.stimulus_start(job['id'])
                run_gdb('''monitor mmw 0xe0042004 0 0x800
monitor halt
monitor sleep 200
printf "PASS: deliberately starved A CPU refill for 200ms; GPIO DMA timer not frozen\\n"
monitor resume
detach
''',ROOT/'build/monitor.elf',directory/'gdb','starve-tx')
                time.sleep(.05)
                result=monitor.stimulus_status()
                assert result['state']==6 and result['underruns']>0,result
                assert monitor.registers(0x40010c08)[0]&0x100
                passed('GDB CPU halt causes explicit TX underrun and physical idle recovery',result)
        report['automated_status']='PASS'
    except Exception as exc:
        report['automated_status']='FAIL'; report['error']=str(exc)
        (directory/'failure.log').write_text(traceback.format_exc())
        try:
            with Monitor() as monitor:
                monitor.command('STOP'); monitor.stimulus_stop()
        except Exception: pass
        raise
    finally:
        save(); print('Evidence:',directory,flush=True)


if __name__=='__main__': main()
