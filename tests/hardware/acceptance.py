#!/usr/bin/env python3
"""Reproducible hardware acceptance. Programs B repeatedly; never installs A.

Requires the resident A already flashed. Restores PWM B on success. Expected
fault/invalid-image cases modify B only. A physical PB12 strap and cold-power
cycle still need manual sign-off; this script does not claim to test those.
"""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time
import traceback
import serial
from client import Monitor, wait_monitor, TRANSIENT_ERRORS
from flash import flash_student
from swd import ROOT, openocd, mailbox_commands, set_mode, tcl_path
from elfcheck import inspect
from gdb_checks import symbols, debug_server, core_check, dma_halted_check
from export import export_capture
from binding import bind_firmware
import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speed', type=int, default=None)
    args = parser.parse_args()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    directory = ROOT/'build/reports'/f'acceptance-{stamp}'
    directory.mkdir(parents=True)
    results = []
    report = {'suite':'R001 safety/capture regression on currently installed monitor','results':results,
              'manual_pending':['PB12-to-GND physical Safe Boot strap', 'cold power cycle',
                                'external signal timing calibration'],
              'scope':'Local software protocol stimuli only; not physical-bus conformance.'}
    def save():
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def passed(name, evidence):
        results.append({'name':name,'status':'PASS','evidence':evidence}); save()
        print('PASS:',name, json.dumps(evidence)[:220],flush=True)
    def flash(name):
        value=flash_student(ROOT/'build'/f'{name}.elf',args.speed,
                            report_dir=directory/f'flash-{name}-{len(results)}')
        if not value['resident_preserved']: raise AssertionError('A modified')
        return value
    def wait_predicate(predicate, timeout=8):
        end=time.monotonic()+timeout
        last=None
        while time.monotonic()<end:
            try:
                with Monitor() as monitor: last=monitor.info()
                if predicate(last): return last
            except TRANSIENT_ERRORS: pass
            time.sleep(.1)
        raise AssertionError(f'Boot condition not reached: {last}')
    try:
        for name in ['student','student_uart','student_lin','student_can','student_fault']:
            inspect(ROOT/'build'/f'{name}.elf')
        passed('sealed ELF preflight', {'images':5})
        base=flash('student')
        info=wait_monitor(True)
        report['version']=info['version']
        assert info['vtor']==0x20000000 and info['clock_error']==0 and info['image_error']==0
        passed('A boots valid B with RAM VTOR',info)
        syms=symbols(ROOT/'build/student.elf')
        with Monitor() as monitor:
            before=monitor.registers(syms['student_loop_count'])[0]
            irq_before=monitor.registers(syms['student_irq_count'])[0]
            monitor.port.write(b'PING\n'*1000)
            for i in range(1000):
                assert monitor.port.readline()==b'PONG\r\n',f'PING reply {i}'
            time.sleep(.1)
            after=monitor.registers(syms['student_loop_count'])[0]
            irq_after=monitor.registers(syms['student_irq_count'])[0]
            assert before!=after and irq_after>irq_before
        passed('USB independent of busy B loop and B IRQs',
               {'loop_before':before,'loop_after':after,'irq_before':irq_before,'irq_after':irq_after,'pings':1000})
        for hz in [10000,100000,500000,1000000]:
            with Monitor() as monitor:
                status,samples=monitor.capture('B',hz,2048,1)
                bits=decode.levels(samples)
                edges=[i for i in range(1,len(bits)) if bits[i]!=bits[i-1]]
                intervals=[b-a for a,b in zip(edges,edges[1:])]
                expected=(72000000/status['ticks'])/2000
                assert len(intervals)>=2 and all(abs(n-expected)<=1 for n in intervals),intervals
                assert status['remaining']==0 and status['dma_flags']&0x20
                regs={'CPAR_CMAR':monitor.registers(0x40020024,2),
                      'RCC_CFGR':monitor.registers(0x40021004)[0]}
                assert regs['CPAR_CMAR'][0]==0x40010c08
                assert 0x20000000<=regs['CPAR_CMAR'][1]<0x20002800
                if hz==100000:
                    export_capture(directory/'pwm',status,samples,info=info,registers=regs)
            passed(f'TIM2 DMA GPIO capture {hz} samples/s',
                   {'status':status,'median_half_period_samples':statistics.median(intervals),'registers':regs})
        # Reject malformed input and bounds without breaking subsequent commands.
        with Monitor() as monitor:
            for cmd in ['CAPTURE B 0 128 1','CAPTURE B 1000001 128 1',
                        'CAPTURE B 10000 2049 1','READ 2048 1','REG 0x40013804 1',
                        'REG 0xffffffff 8']:
                try: monitor.command(cmd)
                except RuntimeError as exc: assert str(exc).startswith('ERR ')
                else: raise AssertionError(f'Accepted invalid request: {cmd}')
            assert monitor.command('PING')=='PONG'
        passed('protocol bounds and side-effect register denylist',{'rejected':6})
        with debug_server(directory/'gdb'):
            output=core_check(directory/'gdb')
        passed('GDB breakpoint/step/watchpoint, PSP and vector ownership',{'log':'gdb/core.log'})
        wait_monitor(True)
        with debug_server(directory/'dma-halted'):
            with Monitor() as monitor:
                monitor.capture_start('B',1000,2048,1)
            output=dma_halted_check(directory/'dma-halted')
        wait_monitor(True)
        with Monitor() as monitor:
            end=time.monotonic()+4
            while time.monotonic()<end:
                status=monitor.capture_status()
                if status['state']==2: break
                time.sleep(.03)
            assert status['state']==2
            samples=monitor.capture_fetch(status)
            assert len(samples)==2048
        passed('DMA advances while CPU halted and A tick frozen',{'log':'dma-halted/dma-halted.log'})
        with Monitor() as monitor: assert monitor.command('MODE SAFE')=='OK reboot'
        safe=wait_predicate(lambda v:v['running']==0 and v['boot_reason']==4)
        with Monitor() as monitor: assert monitor.command('MODE RUN')=='OK reboot'
        wait_monitor(True)
        passed('USB Safe Boot and RUN recovery',safe)
        for kind,baud,hz in [('uart',9600,48000),('lin',9600,96000),('can',20000,200000)]:
            flash('student_'+kind)
            info=wait_monitor(True)
            software_symbols=symbols(ROOT/'build'/('student_'+kind+'.elf'))
            with Monitor() as monitor:
                status,samples=monitor.capture('B',hz,2048,1)
                regs={'TIM4':monitor.registers(0x40000824,3),
                      'APB1ENR':monitor.registers(0x4002101c)[0],
                      'APB2ENR':monitor.registers(0x40021018)[0]}
                regs['max_lateness_ticks']=monitor.registers(software_symbols['student_max_lateness_ticks'])[0]
                assert regs['max_lateness_ticks'] < (72000000/baud)/2
                # Verify USART and CAN hardware clocks remain OFF.
                assert not (regs['APB1ENR'] & ((1<<25)|(1<<17)|(1<<18)))
                assert not (regs['APB2ENR'] & (1<<14))
            decoded=getattr(decode,kind)(decode.levels(samples),72000000/status['ticks'],baud)
            # Preserve raw measurements even when the decoder assertion fails.
            export_capture(directory/kind,status,samples,decoded,info,regs)
            if kind=='uart':
                assert b'Hello BluePill\r\n' in bytes(v['value'] for v in decoded),decoded
            elif kind=='lin':
                assert decoded and all(v['id']==0x12 and v['data']=='3456' and
                                       v['checksum_ok'] and v['parity_ok'] for v in decoded),decoded
            else:
                assert decoded and all(v['id']==0x123 and v['data']=='dead' and
                                       v['crc_ok'] and not v['ack'] for v in decoded),decoded
            passed('software '+kind.upper()+' capture and decode',{'frames':len(decoded),'decoded':decoded[:3]})
        flash('student_fault')
        fault=wait_predicate(lambda v:v['boot_reason']==5 and v['running']==0,timeout=10)
        assert 0x08006000<=fault['fault_pc']<0x08010000 and fault['fault_cfsr']&(1<<16)
        passed('B undefined-instruction fault records PC and boots Safe',fault)
        # Deliberate fault injection bypasses release preflight ONLY in this test.
        original=(ROOT/'build/student.bin').read_bytes()
        for label,modify,error in [('missing-manifest',lambda data:data.__setitem__(slice(0x200,0x240),b'\xff'*64),1),
                                   ('bad-crc',lambda data:data.__setitem__(-1,data[-1]^1),5)]:
            data=bytearray(original); modify(data)
            image=directory/(label+'.bin'); image.write_bytes(data)
            openocd([f'program {tcl_path(image)} 0x08006000 verify',
                     *mailbox_commands(False),'reset run'],args.speed,directory/(label+'.log'))
            invalid=wait_predicate(lambda v:v['image_error']==error and v['boot_reason']==2)
            assert invalid['running']==0
            passed('boot rejects '+label,invalid)
        final=flash('student')
        assert final['a_sha256_before']==base['a_sha256_before']
        final_info=wait_monitor(True)
        passed('A preserved across all B images and recovery, PWM B restored',
               {'a_sha256':final['a_sha256_after'],'info':final_info})
        report['firmware_binding']=bind_firmware(directory,args.speed)
        report['automated_status']='PASS'
        report['release_status']='CANDIDATE; manual gates pending'
        save()
        print('AUTOMATED HARDWARE CHECKS PASSED. Manual gates remain. Report:',directory,flush=True)
        print('Evidence:',directory,flush=True)
        return 0
    except Exception:
        report['automated_status']='FAIL'
        report['failure']=traceback.format_exc()
        save()
        print(report['failure'],flush=True)
        # Leave a responsive monitor for investigation; preserve crash evidence.
        try: set_mode(True,args.speed,directory/'failure-safe.log')
        except Exception: pass
        print('FAILED; see',directory,flush=True)
        print('Evidence:',directory,flush=True)
        return 1


if __name__=='__main__': raise SystemExit(main())
