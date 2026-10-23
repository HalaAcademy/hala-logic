"""Hardware checks via real OpenOCD/GDB, using B symbols and A memory layout."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import time
from elftools.elf.elffile import ELFFile
from swd import ROOT, CONFIG
from config import tool, settings


def symbols(path):
    with open(path, 'rb') as stream:
        elf = ELFFile(stream)
        table = elf.get_section_by_name('.symtab')
        return {symbol.name: int(symbol['st_value']) for symbol in table.iter_symbols()}


@contextmanager
def debug_server(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'openocd.log').open('w') as log:
        process = subprocess.Popen([tool('openocd'), '-f', str(CONFIG), '-c', f"adapter speed {settings()['swd_khz']}", '-c', f"gdb_port {settings()['gdb_endpoint'].rsplit(':',1)[1]}"], stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('OpenOCD server exited; see log')
                if f"Listening on port {settings()['gdb_endpoint'].rsplit(':',1)[1]}" in (directory/'openocd.log').read_text():
                    break
                time.sleep(.05)
            else:
                raise RuntimeError('OpenOCD GDB server did not start')
            yield
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


def run_gdb(commands, elf, directory, name):
    directory = Path(directory)
    script = directory / (name + '.gdb')
    script.write_text('set pagination off\nset confirm off\nset remotetimeout 10\n'
                      f"target extended-remote {settings()['gdb_endpoint']}\n" + commands + '\nquit 0\n')
    result = subprocess.run([tool('gdb'),'-q','-batch','-x',str(script),str(elf)],
                            capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    (directory / (name + '.log')).write_text(output)
    if result.returncode or 'PASS:' not in output or 'FAIL:' in output:
        raise RuntimeError(f'GDB check {name} failed:\n{output}')
    return output


def core_check(directory):
    commands = '''monitor reset halt
hbreak main
continue
if (*(unsigned int *)0xe000ed08) != 0x20000000
 echo FAIL: VTOR is not A RAM vector table\n
 quit 1
end
if $control != 2
 echo FAIL: B is not privileged Thread mode on PSP\n
 quit 1
end
if $psp <= 0x20003000 || $psp > 0x20005000
 echo FAIL: B PSP out of partition\n
 quit 1
end
if (*(unsigned int *)0x20000090) < 0x08000000 || (*(unsigned int *)0x20000090) >= 0x08006000
 echo FAIL: USB vector is not owned by A\n
 quit 1
end
if (*(unsigned int *)0x200000b8) < 0x08006000 || (*(unsigned int *)0x200000b8) >= 0x08010000
 echo FAIL: TIM4 vector is not forwarded to B\n
 quit 1
end
printf "PASS: B main breakpoint, CONTROL=%u PSP=%#x MSP=%#x, VTOR A + TIM4 B\\n", $control, $psp, $msp
delete breakpoints
set $pc_before = $pc
stepi
if $pc == $pc_before
 echo FAIL: step did not advance\n
 quit 1
end
hbreak TIM4_IRQHandler
continue
if ($xPSR & 0x1ff) != 46
 echo FAIL: not executing TIM4 exception\n
 quit 1
end
printf "PASS: forwarded B TIM4 ISR breakpoint, IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
set $watch_before=student_loop_count
watch -location student_loop_count
continue
if student_loop_count != $watch_before + 1
 echo FAIL: RAM watchpoint did not stop on next Thread counter write\\n
 quit 1
end
printf "PASS: B RAM hardware watchpoint, Thread loop count=%u\\n", student_loop_count
delete breakpoints
monitor reset run
detach
'''
    output=run_gdb(commands, ROOT/'build/student.elf', directory, 'core')
    if 'Old value =' not in output or 'New value =' not in output:
        raise RuntimeError('GDB hardware watchpoint did not report old/new values')
    return output


def dma_halted_check(directory):
    ticks = symbols(ROOT/'build/monitor.elf')['monitor_ticks']
    commands = f'''monitor mmw 0xe0042004 0 0x700
monitor halt
set $before = *(unsigned int *)0x40020020
set $ticks_before = *(unsigned int *){ticks:#x}
monitor sleep 250
set $after = *(unsigned int *)0x40020020
if $before == 0 || $after >= $before
 echo FAIL: DMA CNDTR did not decrease while CPU halted\n
 quit 1
end
if *(unsigned int *){ticks:#x} != $ticks_before
 echo FAIL: CPU tick moved while supposedly halted\n
 quit 1
end
if $before - $after < 200 || $before - $after > 300
 echo FAIL: DMA sample progress inconsistent with 1 kHz over 250 ms\n
 quit 1
end
printf "PASS: CPU halted, monitor ticks frozen=%u, DMA CNDTR %u -> %u\\n", $ticks_before, $before, $after
monitor resume
detach
'''
    return run_gdb(commands, ROOT/'build/student.elf', directory, 'dma-halted')

if __name__ == '__main__':
    import argparse
    import datetime
    parser = argparse.ArgumentParser(description='GDB acceptance for the installed PWM student sample. Close other OpenOCD servers first.')
    parser.parse_args()
    directory = ROOT/'build/reports'/('gdb-manual-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    print('Requires PWM B matching build/student.elf; run make flash first.',flush=True)
    with debug_server(directory):
        print(core_check(directory))
    print('Evidence:', directory)
