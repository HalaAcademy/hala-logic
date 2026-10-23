#!/usr/bin/env python3
"""Real GDB main/step/ISR/watchpoint and stack guards for every non-fault B ELF."""

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
from gdb_checks import debug_server,run_gdb
from swd import ROOT,set_mode

IMAGES=['student','student_uart','student_lin','student_can','student_uart_rx',
        'student_lin_rx','student_can_rx','student_canfd_rx','student_canfd_tx',
        'student_flexray_rx','student_flexray_rx_b','student_flexray_tx','student_flexray_tx_b',
        'student_can2_tx','student_can2_tx_ext','student_can2_tx_rtr','student_can2_tx_ext_rtr','student_canfd_tx_ext']

COMMANDS='''monitor reset halt
hbreak main
continue
if $control != 2 || $psp <= 0x20004c00 || $psp > 0x20005000
 echo FAIL: B CONTROL/PSP partition\\n
 quit 1
end
if *(unsigned int *)0xe000ed08 != 0x20000000
 echo FAIL: RAM VTOR not A\\n
 quit 1
end
if *(unsigned int *)0x20000090 < 0x08000000 || *(unsigned int *)0x20000090 >= 0x08006000
 echo FAIL: USB vector outside A\\n
 quit 1
end
if *(unsigned int *)0x2000007c < 0x08000000 || *(unsigned int *)0x2000007c >= 0x08006000
 echo FAIL: output DMA vector outside A\\n
 quit 1
end
if *(unsigned int *)0x200000b8 < 0x08006000 || *(unsigned int *)0x200000b8 >= 0x08010000
 echo FAIL: B timer vector outside B\\n
 quit 1
end
printf "PASS: B main breakpoint CONTROL=%u PSP=%#x MSP=%#x and vector ownership\\n",$control,$psp,$msp
delete breakpoints
set $before=$pc
stepi
if $pc == $before
 echo FAIL: B instruction step did not advance\\n
 quit 1
end
printf "PASS: B stepi PC=%#x\\n",$pc
hbreak TIM4_IRQHandler
continue
if ($xPSR & 0x1ff) != 46 || $msp < 0x20002800 || $msp > 0x20003000
 echo FAIL: B IRQ/exception MSP\\n
 quit 1
end
printf "PASS: B TIM4 ISR IPSR=%u MSP=%#x\\n",($xPSR&0x1ff),$msp
delete breakpoints
set $watch_before=student_loop_count
watch -location student_loop_count
continue
if student_loop_count != $watch_before + 1
 echo FAIL: RAM watchpoint did not stop on next write\\n
 quit 1
end
printf "PASS: B RAM hardware watchpoint, before=%u after=%u\\n",$watch_before,student_loop_count
delete breakpoints
monitor reset run
detach
'''


def main():
    import argparse
    from config import settings
    parser=argparse.ArgumentParser(description='Kiểm GDB các ELF ứng dụng đã build, không cài monitor.')
    parser.add_argument('--images',nargs='+',choices=IMAGES,default=IMAGES)
    args=parser.parse_args();images=args.images;speed=settings()['swd_khz']
    output=ROOT/'build/reports'/('gdb-examples-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True);(output/'firmware').mkdir()
    report={'images_requested':images,'transport':f'ST-Link direct DAP SWD {speed} kHz','results':[]}
    def save():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        for name in images:
            path=ROOT/'build'/f'{name}.elf'
            shutil.copy2(path,output/'firmware'/path.name)
            record=flash_student(path,speed,report_dir=output/f'flash-{name}')
            wait_monitor(True)
            with debug_server(output/name):
                log=run_gdb(COMMANDS,path,output/name,'main-isr-watch')
            assert 'Old value =' in log and 'New value =' in log,'Missing GDB watchpoint stop/value evidence'
            wait_monitor(True)
            with Monitor() as monitor:
                stack=json.loads(monitor.command('STACK'))
                assert stack['a_msp_unwritten_bytes']>=256,stack
                assert stack['b_psp_unwritten_bytes']>=128,stack
                assert monitor.command('PING')=='PONG'
            report['results'].append({'name':name,'status':'PASS','stack':stack,
                'A_preserved':record['resident_preserved'],'gdb_log':str(output/name/'main-isr-watch.log')})
            save();print('PASS: GDB main/step/ISR/watchpoint + stack guards',name,stack,flush=True)
        flash_student(ROOT/'build/student.elf',speed,report_dir=output/'restore-pwm')
        wait_monitor(True);report['automated_status']='PASS'
    except Exception as exc:
        report.update(automated_status='FAIL',error=str(exc))
        (output/'failure.log').write_text(traceback.format_exc())
        try:set_mode(True,speed,output/'safe.log')
        except Exception:pass
        raise
    finally:
        save();print('Evidence:',output,flush=True)


if __name__=='__main__':main()
