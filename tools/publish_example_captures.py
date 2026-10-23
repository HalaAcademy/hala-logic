#!/usr/bin/env python3
"""Chọn capture thật từ suite PASS, kiểm hash/ELF/giải mã rồi xuất dữ liệu hướng dẫn."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ('host', 'tools/device')]
from config import catalog
from session import Capture
import measurements


def publish(suite):
    suite = Path(suite).resolve()
    report = json.loads((suite/'report.json').read_text())
    if report['overall'] != 'PASS_IMPLEMENTED_SCOPE':
        raise ValueError('Chỉ xuất từ một suite đã PASS đầy đủ phạm vi triển khai.')
    steps = {item['step']: item for item in report['steps']}
    if any(item['status'] != 'PASS' or item['exit_code'] for item in steps.values()):
        raise ValueError('Suite có bước chưa PASS.')
    gdb = Path(steps['gdb_examples_acceptance']['evidence'])
    gdb_report = json.loads((gdb/'report.json').read_text())
    debugged = {item['name'] for item in gdb_report['results'] if item['status'] == 'PASS'}
    records = []
    public = ROOT/'examples/captures/by-example'
    public.mkdir(parents=True, exist_ok=True)
    for entry in catalog():
        profile = json.loads((ROOT/'configs/waveforms'/f"{entry['key']}.json").read_text())
        step = steps[profile['suite_step']]
        evidence = Path(step['evidence'])
        child = json.loads((evidence/'report.json').read_text())
        image = entry['image']
        record = {'example':entry['key'], 'elf':f'build/{image}.elf',
                  'elf_sha256':hashlib.sha256((ROOT/'build'/f'{image}.elf').read_bytes()).hexdigest(),
                  'test_module':profile['test_module'], 'test_result':child['automated_status'],
                  'profile':f"configs/waveforms/{entry['key']}.json"}
        if entry['direction'] == 'fault':
            fault = next(item for item in child['results']
                         if item['name'] == 'B undefined-instruction fault records PC and boots Safe')
            if fault['status'] != 'PASS':
                raise ValueError('Fault recovery chưa PASS.')
            record['fault_evidence'] = fault['evidence']
            record['capture'] = None
            record['note'] = 'Intentional fault; no communication waveform expected.'
            records.append(record)
            continue
        if image not in debugged or (gdb/'firmware'/f'{image}.elf').read_bytes() != (ROOT/'build'/f'{image}.elf').read_bytes():
            raise ValueError('ELF hiện tại không khớp lượt GDB: ' + image)
        src = evidence/(profile['capture_stem']+'.json')
        metadata = json.loads(src.read_text())
        raw = src.with_suffix('.bin').read_bytes()
        status = metadata['capture']
        digest = hashlib.sha256(raw).hexdigest()
        if digest != metadata['raw_sha256'] or len(raw) != status['count']*2 or status['state'] != 2 or status.get('lost',0):
            raise ValueError('Capture INVALID: ' + str(src))
        capture = Capture(protocol=profile['protocol'], port='ABC'[status['port']],
                          mask=status['mask'], bit=profile['decode_bit'],
                          hz=round(72000000/status['ticks']), count=status['count'],
                          baud=profile['baud'], data_baud=profile['data_baud'] or 2000,
                          channel=profile['channel'] or 'A', stream=bool(status.get('stream')))
        capture.validate()
        samples = list(struct.unpack('<'+'H'*status['count'],raw))
        decoded = capture.decode(samples,status['ticks'])
        if profile['protocol'] != 'GPIO':
            if not decoded:
                raise ValueError('Không giải mã được frame: ' + entry['key'])
            for frame in decoded:
                if any(not value for key,value in frame.items() if key.endswith('_ok') and key != 'ack_ok'):
                    raise ValueError('Frame mẫu có lỗi: ' + entry['key'])
        details = {'protocol':capture.protocol,'decode_bit':capture.bit,'baud':capture.baud,
                   'data_baud':capture.data_baud,'channel':capture.channel}
        output = {'capture':status,'monitor':None,'registers_after_capture':details,
                  'raw_sha256':digest,'decoded':decoded,'timing_note':metadata['timing_note']}
        target = public/(entry['key']+'.json')
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        target.with_suffix('.bin').write_bytes(raw)
        record.update(capture=str(target.relative_to(ROOT)),raw_sha256=digest,
                      settings=asdict(capture),decoded_frames=len(decoded),gdb_result='PASS',
                      measurements=measurements.channel(samples,72000000/status['ticks'],capture.bit))
        records.append(record)
    result = {'date':suite.name.removeprefix('suite-'),'status':'PASS_IMPLEMENTED_EXAMPLES',
              'scope':'18 communication/PWM examples plus intentional fault recovery; not all master-plan modes',
              'suite_id':suite.name,'records':records,
              'manual_pending':report['manual_pending']}
    destination=ROOT/'docs/review/waveforms-20261023.json'
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Đã kiểm và xuất {len(records)-1} capture thật, {len(records)} kết quả example.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite',type=Path,help='Thư mục suite đã PASS, ví dụ build/reports/suite-YYYYMMDD-HHMMSS')
    args=parser.parse_args()
    publish(args.suite)
