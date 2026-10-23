#!/usr/bin/env python3
"""B FD/FR software TX on physical PB0 + real GDB and raw captures, no jumpers."""

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
import canfd,flexray


def main():
    directory=ROOT/'build/reports'/('advanced-tx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True);(directory/'firmware').mkdir()
    report={'scope':'B software FD 11/29 TX with ACK observer; FR static frame TX channel A/B separately',
            'excluded':'FD arbitration/retry/error-confinement; FR cluster startup/schedule/simultaneous channels',
            'results':[]}
    for image in ('monitor','student_canfd_tx','student_canfd_tx_ext','student_flexray_tx','student_flexray_tx_b'):
        for suffix in ('elf','bin'):
            shutil.copy2(ROOT/'build'/f'{image}.{suffix}',directory/'firmware'/f'{image}.{suffix}')
    def save():(directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def passed(name,result):
        report['results'].append({'name':name,'status':'PASS','evidence':result});save()
        print('PASS:',name,flush=True)
    try:
        for extended in (False,True):
            suffix='-ext' if extended else ''
            image='student_canfd_tx'+('_ext' if extended else '')
            identifier=0x12345678 if extended else 0x5aa
            syms=symbols(ROOT/'build'/f'{image}.elf')
            flash_student(ROOT/'build'/f'{image}.elf',None,report_dir=directory/('flash-fd-tx'+suffix))
            wait_monitor(True)
            with Monitor() as monitor:
                # A executes only generic edge wait and timed GPIO levels.
                _,expected=canfd.frame(identifier,bytes(range(64)),extended=extended)
                ack=expected['ack_quarter_from_sof']
                bits=[0x400]*(expected['active_quarters']+48)
                bits[ack:ack+4]=[0]*4
                job=monitor.stimulus_upload(bits,64000,mask=0x400,idle=0x400,repeat=16)
                monitor.bridge(0x401)
                before=monitor.registers(syms['tx_ack_count'])[0]
                status,samples=monitor.capture_stream('B',16000,32768,0x501,
                    on_start=lambda:monitor.stimulus_arm(job['id'],idle_ticks=11*64))
                frames=canfd.decode([(s>>8)&1 for s in samples],16000)
                txframes=canfd.decode([(s>>0)&1 for s in samples],16000)
                state=monitor.stimulus_status()
                after=monitor.registers(syms['tx_ack_count'])[0]
                no_ack=monitor.registers(syms['tx_no_ack_count'])[0]
                export_capture(directory/('canfd-B-TX-ACK'+suffix),status,samples,frames,monitor.info(),
                               {'peer':state,'B_ack_before':before,'B_ack_after':after,'B_no_ack':no_ack})
                assert state['state']==3 and not state['underruns'],state
                assert len(frames)>=2 and all(f['crc_ok'] and f['stuff_count_ok'] and f['format_ok'] for f in frames),frames
                assert all(f['id']==identifier and f['extended']==extended and f['data']==bytes(range(64)).hex() for f in frames),frames
                assert sum(f['ack'] for f in frames)==1 and all(not f['ack'] for f in txframes),frames
                assert after-before==1 and no_ack>0,(before,after,no_ack)
                passed(f'B GPIO FD {29 if extended else 11}-bit TX64 BRS/CRC21 and host ACK',
                       {'bus_frames':frames,'tx_frames':txframes,'peer':state,
                        'B_ack_before':before,'B_ack_after':after,'B_no_ack':no_ack})
                monitor.stimulus_stop()
            gdb_dir=directory/('gdb-fd'+suffix)
            with debug_server(gdb_dir):
                run_gdb('''monitor halt
if tx_ack_count != 1 || tx_no_ack_count == 0
 echo FAIL: FD B did not distinguish ACK/no-ACK\\n
 quit 1
end
printf "PASS: B FD TX ACK=%u missing=%u frames=%u\\n", tx_ack_count, tx_no_ack_count, student_frames
hbreak TIM4_IRQHandler
continue
printf "PASS: B FD TX TIM4 ISR IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
''',ROOT/'build'/f'{image}.elf',gdb_dir,'fd-tx')
                log=run_gdb(COMMANDS,ROOT/'build'/f'{image}.elf',gdb_dir,'main-isr-watch')
                assert 'Old value =' in log and 'New value =' in log,'Missing watchpoint Old/New evidence'
        for channel in ('A','B'):
            image='student_flexray_tx'+('_b' if channel=='B' else '')
            flash_student(ROOT/'build'/f'{image}.elf',None,report_dir=directory/f'flash-fr-{channel}')
            wait_monitor(True)
            with Monitor() as monitor:
                status,samples=monitor.capture_stream('B',16000,98304,1)
                frames=flexray.decode([(s>>0)&1 for s in samples],16000,channel=channel)
                syms=symbols(ROOT/'build'/f'{image}.elf')
                count=monitor.registers(syms['student_frames'])[0]
                export_capture(directory/f'flexray-B-TX-{channel}',status,samples,frames,monitor.info())
                assert frames and all(f['header_crc_ok'] and f['frame_crc_ok'] and f['format_ok'] for f in frames),frames
                assert all(f['id']==0x123 and f['cycle']==7 and f['data']==bytes(range(254)).hex() for f in frames),frames
                assert count>=2,count
                passed(f'B GPIO FlexRay static FRAME TX channel {channel}, 254 bytes',{'frames':frames,'B_frame_counter':count})
            with debug_server(directory/f'gdb-fr-{channel}'):
                run_gdb('''monitor halt
if student_frames < 2
 echo FAIL: FR B did not advance frame counter\\n
 quit 1
end
printf "PASS: GDB FR B frames=%u loops=%u\\n", student_frames, student_loop_count
hbreak TIM4_IRQHandler
continue
printf "PASS: B FR TX TIM4 ISR IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
''',ROOT/'build'/f'{image}.elf',directory/f'gdb-fr-{channel}','fr-tx')
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
