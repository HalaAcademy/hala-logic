#!/usr/bin/env python3
"""FR teaching STATIC FRAME RX, channel seeds separately, not cluster conformance."""

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
from export import export_capture
import flexray


def main():
    directory=ROOT/'build/reports'/('flexray-rx-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True);(directory/'firmware').mkdir()
    report={'scope':'FR21A-TEACH static frame codec RX only; channel A/B tested SEPARATELY',
            'excluded':'cluster startup/synchronization, TDMA/minislot schedule, simultaneous two-channel redundancy',
            'fixture':'physical peer PB10 relayed into physical PB8, no jumper','results':[]}
    for image in ('monitor','student_flexray_rx','student_flexray_rx_b'):
        for suffix in ('elf','bin'):
            shutil.copy2(ROOT/'build'/f'{image}.{suffix}',directory/'firmware'/f'{image}.{suffix}')
    def save():(directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        for channel in ('A','B'):
            image='student_flexray_rx'+('_b' if channel=='B' else '')
            syms=symbols(ROOT/'build'/f'{image}.elf')
            def state(m):
                result={s:m.registers(syms[s])[0] for s in ['rx_count','rx_errors','header_errors',
                        'frame_errors','format_errors','rx_id','rx_length','rx_cycle','student_max_lateness_ticks']}
                raw=b'';base=syms['rx_data']
                for offset in range(0,256,32):raw+=struct.pack('<8I',*m.registers(base+offset,8))
                result['data']=raw[:254].hex();return result
            flash_student(ROOT/'build'/f'{image}.elf',None,report_dir=directory/f'flash-{channel}')
            wait_monitor(True)
            cases=[('empty',1,b'',0,{}),('two-byte',0x123,b'\x34\x56',1,{}),
                   ('id-cycle-max',2047,bytes(range(16)),63,{}),
                   ('payload-max',7,bytes(range(254)),32,{}),
                   ('bad-header',0x123,b'\x34\x56',1,{'corrupt_header':True}),
                   ('bad-frame',0x123,b'\x34\x56',1,{'corrupt_crc':True}),
                   ('wrong-channel',0x123,b'\x34\x56',1,{'channel':'B' if channel=='A' else 'A'}),
                   ('recovery',3,b'\xff\x00',0,{})]
            with Monitor() as monitor:
                for label,identifier,data,cycle,opts in cases:
                    name=channel+'-'+label;options={'channel':channel,**opts}
                    levels,expected=flexray.frame(identifier,data,cycle=cycle,**options)
                    job=monitor.stimulus_upload(levels,16000,mask=0x400,idle=0x400,repeat=16)
                    monitor.bridge(0x400);before=state(monitor)
                    count=((len(levels)*16+2047)//1024+1)*1024
                    status,samples=monitor.capture_stream('B',16000,count,0x501,
                        on_start=lambda:monitor.stimulus_start(job['id']))
                    after=state(monitor);tx=monitor.stimulus_status()
                    frames=flexray.decode([(v>>8)&1 for v in samples],16000,channel=channel)
                    export_capture(directory/name,status,samples,frames,monitor.info(),
                                   {'before':before,'after':after,'stimulus':tx,'expected':expected})
                    result={'name':name,'expected':expected,'before':before,'after':after,'frames':frames,'tx':tx}
                    (directory/(name+'-observed.json')).write_text(json.dumps(result,indent=2)+'\n')
                    assert tx['state']==3 and not tx['underruns'],result
                    assert len(frames)==1 and frames[0]['data']==data.hex(),result
                    frame=frames[0]
                    if label=='bad-header':
                        assert not frame['header_crc_ok'] and after['header_errors']==before['header_errors']+1,result
                        assert after['rx_count']==before['rx_count'],result
                    elif label in ('bad-frame','wrong-channel'):
                        assert not frame['frame_crc_ok'] and after['frame_errors']==before['frame_errors']+1,result
                        assert after['rx_count']==before['rx_count'],result
                    else:
                        assert frame['format_ok'] and frame['header_crc_ok'] and frame['frame_crc_ok'],result
                        assert after['rx_count']==before['rx_count']+1,result
                        assert after['rx_id']==identifier and after['rx_length']==len(data),result
                        assert after['rx_cycle']==cycle and after['data'][:len(data)*2]==data.hex(),result
                        assert after['rx_errors']==before['rx_errors'],result
                    result['status']='PASS';report['results'].append(result);save()
                    print('PASS: FlexRay static FRAME software RX',name,flush=True)
                    monitor.bridge(0)
            with debug_server(directory/f'gdb-{channel}'):
                run_gdb('''monitor halt
if rx_count != 5 || header_errors != 1 || frame_errors != 2
 echo FAIL: FlexRay teaching B variables incorrect\\n
 quit 1
end
printf "PASS: GDB FR teaching B RX=%u header-errors=%u frame-errors=%u ID=%u cycle=%u\\n", rx_count, header_errors, frame_errors, rx_id, rx_cycle
hbreak TIM4_IRQHandler
continue
printf "PASS: B FR software sampling ISR IPSR=%u\\n", ($xPSR & 0x1ff)
delete breakpoints
monitor resume
detach
''',ROOT/'build'/f'{image}.elf',directory/f'gdb-{channel}','flexray-rx')
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
