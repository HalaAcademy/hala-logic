#!/usr/bin/env python3
"""Real-pad RX/TX acceptance; no jumpers or virtual GPIO. Requires dev1 A.

Installs B UART RX using SWD, captures PB8 input + PB0 app reply, then uses
GDB to inspect ordinary B variables/instructions. Keeps raw failures too.
Restores PWM B on success; enters SWD Safe on an unexpected failure.
"""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import argparse
import datetime
import json
from pathlib import Path
import struct
import time
import traceback
from client import Monitor, wait_monitor
from flash import flash_student
from gdb_checks import symbols, debug_server, run_gdb
from swd import ROOT, set_mode
from export import export_capture
import decode
import stimulus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speed', type=int, default=None)
    args = parser.parse_args()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    directory = ROOT/'build/reports'/f'no-wire-{stamp}'
    directory.mkdir(parents=True)
    report = {'version': 'R002-dev1', 'fixture': 'ONE MCU; NO JUMPERS; REAL GPIO',
              'results': [], 'manual_pending': ['cold power', 'physical Safe strap',
                                                'absolute timing calibration']}
    def save():
        (directory/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def passed(name, evidence):
        report['results'].append({'name': name, 'status': 'PASS', 'evidence': evidence})
        save(); print('PASS:', name, flush=True)
    syms = symbols(ROOT/'build/student_uart_rx.elf')
    def app(monitor):
        return {name: monitor.registers(syms[name])[0] for name in
                ['rx_count','rx_errors','rx_false_starts','rx_dropped',
                 'student_loop_count','student_irq_count','student_max_lateness_ticks']}
    def acquire(monitor, name, levels, hz=1000):
        job = monitor.stimulus_upload(levels, hz)
        before = app(monitor)
        monitor.capture_start('B', 16000, 2048, 0x101)
        started = monitor.stimulus_start(job['id'])
        # Exercise the control plane WHILE B receives/transmits and DMA runs.
        for _ in range(50):
            assert monitor.command('PING') == 'PONG'
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            status = monitor.capture_status()
            if status['state'] != 1: break
            time.sleep(.01)
        samples = monitor.capture_fetch(status)
        after = app(monitor)
        tx = monitor.stimulus_status()
        deadline = time.monotonic()+1
        while tx['state'] == 2 and time.monotonic() < deadline:
            time.sleep(.005); tx = monitor.stimulus_status()
        assert tx['state'] == 3 and tx['dma_flags'] & (3 << 17) and not tx['underruns'], tx
        actual_rx = decode.uart(decode.levels(samples,8),16000,1000)
        actual_tx = decode.uart(decode.levels(samples,0),16000,1000)
        export_capture(directory/name, status, samples,
                       actual_rx, monitor.info(), {'app_before':before, 'app_after':after})
        (directory/(name+'-reply.json')).write_text(json.dumps(actual_tx,indent=2)+'\n')
        result = {'before':before, 'after':after, 'stimulus':started,
                  'completed':tx, 'input':[x['value'] for x in actual_rx],
                  'reply':[x['value'] for x in actual_tx]}
        (directory/(name+'-observed.json')).write_text(json.dumps(result,indent=2)+'\n')
        return result
    try:
        info = wait_monitor(True)
        assert 'R002-dev' in info['version'], info
        record = flash_student(ROOT/'build/student_uart_rx.elf',args.speed,
                               report_dir=directory/'flash-uart-rx')
        assert record['resident_preserved']
        wait_monitor(True)
        with Monitor() as monitor:
            caps = monitor.capabilities()
            assert caps['no_wire_same_pad'] and caps['tx_mask'] == 0x500
            passed('capability and SWD B-only preservation', {'caps':caps,'flash':record})
            for cmd in ['TXCONFIG 0 256 256 0','TXCONFIG 100001 256 256 0',
                        'TXCONFIG 1000 4096 4096 0','TXCONFIG 1000 256 512 0',
                        'TXCONFIG 1000 256 256 2','TXSTART 999999']:
                try: monitor.command(cmd)
                except RuntimeError as exc: assert str(exc).startswith('ERR ')
                else: raise AssertionError(f'Accepted invalid job: {cmd}')
            job = monitor.stimulus_upload([256,0], 1000, idle=0)  # valid idle-low job
            assert job['loaded'] == 2
            monitor.stimulus_stop()
            monitor.command('TXCONFIG 1000 256 256 0')
            for cmd in ['TXDATA 1 0100','TXDATA 0 000z','TXDATA 0 0200',
                        'TXDATA 0 010','TXSTART 999999']:
                try: monitor.command(cmd)
                except RuntimeError: pass
                else: raise AssertionError(f'Accepted invalid upload: {cmd}')
            assert monitor.stimulus_status()['loaded'] == 0
            passed('stimulus denylist, ranges and atomic chunk validation',{'rejected':11})
            first = acquire(monitor,'uart-rx-HELLO',stimulus.uart(b'HELLO'))
            assert first['input'] == list(b'HELLO'), first
            assert first['reply'] == [b ^ 0x20 for b in b'HELLO'], first
            assert first['after']['rx_count'] - first['before']['rx_count'] == 5, first
            assert first['after']['rx_errors'] == first['before']['rx_errors'], first
            assert first['after']['student_loop_count'] != first['before']['student_loop_count']
            passed('physical PB8 RX and independent PB0 app response, busy B + USB',first)
            # Literal waveform, intentionally NOT built by host UART encoder.
            bits = [1]*12+[0,1,0,1,0,1,0,1,0,0]+[1]*12 # 0x55, stop LOW
            bad = acquire(monitor,'uart-bad-stop',[256 if b else 0 for b in bits])
            assert bad['after']['rx_count'] == bad['before']['rx_count'], bad
            assert bad['after']['rx_errors'] == bad['before']['rx_errors']+1, bad
            assert bad['reply'] == [], bad
            passed('B rejects literal malformed stop, no false app delivery',bad)
            recovery = acquire(monitor,'uart-rx-recovery',stimulus.uart(bytes([0,255,85,170])))
            assert recovery['input'] == [0,255,85,170], recovery
            assert recovery['reply'] == [32,223,117,138], recovery
            assert recovery['after']['rx_count'] - recovery['before']['rx_count'] == 4
            assert recovery['after']['rx_errors'] == recovery['before']['rx_errors']
            passed('RX recovery and extreme data patterns',recovery)
            # Check that retrying START on a completed job cannot replay it.
            count = app(monitor)['rx_count']
            monitor.stimulus_start(recovery['completed']['id'])
            time.sleep(.15)
            assert app(monitor)['rx_count'] == count
            passed('idempotent START cannot retransmit completed job',{'rx_count':count})
            regs = {'gpio_crh':monitor.registers(0x40010c04)[0],
                    'capture_cpar_cmar':monitor.registers(0x40020024,2),
                    'tx_cpar_cmar':monitor.registers(0x40020060,2),
                    'apb2enr':monitor.registers(0x40021018)[0],
                    'apb1enr':monitor.registers(0x4002101c)[0]}
            assert regs['gpio_crh'] & 15 == 2 # A owns PB8 drive, input buffer active
            assert regs['capture_cpar_cmar'][0] == 0x40010c08
            assert regs['tx_cpar_cmar'][0] == 0x40010c10
            assert not regs['apb2enr'] & (1<<14)
            assert not regs['apb1enr'] & ((1<<17)|(1<<18)|(1<<25))
            passed('real IDR capture/BSRR DMA addresses; USART/bxCAN clocks off',regs)
        # Debug only AFTER timing assertions: halt invalidates a realtime run.
        expected = recovery['after']['rx_count']
        commands = f'''monitor halt
if rx_count != {expected}
 echo FAIL: B RX variable disagrees with live USB observation\\n
 quit 1
end
if *(unsigned int *)0xe000ed08 != 0x20000000
 echo FAIL: VTOR is not A SRAM\\n
 quit 1
end
if *(unsigned int *)0x2000007c < 0x08000000 || *(unsigned int *)0x2000007c >= 0x08006000
 echo FAIL: DMA1 CH5 vector not A\\n
 quit 1
end
printf "PASS: ordinary B RX variables count=%u errors=%u, GPIO_IDR=%#x\\n", rx_count, rx_errors, *(unsigned int *)0x40010c08
hbreak TIM4_IRQHandler
continue
if ($xPSR & 0x1ff) != 46
 echo FAIL: B timer ISR not reached\\n
 quit 1
end
printf "PASS: B timer ISR breakpoint, IPSR=%u MSP=%#x PSP=%#x\\n", ($xPSR & 0x1ff), $msp, $psp
delete breakpoints
monitor resume
detach
'''
        with debug_server(directory/'gdb'):
            run_gdb(commands,ROOT/'build/student_uart_rx.elf',directory/'gdb','rx-isr')
        passed('independent GDB B variables and real TIM4 ISR breakpoint',{'log':'gdb/rx-isr.log'})
        record = flash_student(ROOT/'build/student.elf',args.speed,
                               report_dir=directory/'restore-pwm')
        wait_monitor(True)
        passed('PWM B restored; full A Flash preserved again',record)
        report['automated_status'] = 'PASS'
    except Exception as exc:
        report['automated_status'] = 'FAIL'
        report['error'] = str(exc)
        (directory/'failure.log').write_text(traceback.format_exc())
        try: set_mode(True,args.speed,directory/'failure-safe.log')
        except Exception as safe_exc: report['safe_error'] = str(safe_exc)
        raise
    finally:
        save()
        print('Evidence:',directory,flush=True)


if __name__ == '__main__': main()
