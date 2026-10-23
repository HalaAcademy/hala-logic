#!/usr/bin/env python3
"""Sequential real-board suite, fail closed, retain failure evidence, no implicit A flash."""

import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(_PROJECT / folder) for folder in ('host', 'tools/device', 'tests/hardware')]
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from client import wait_monitor
from swd import ROOT

STEPS=['gdb_examples_acceptance','acceptance','no_wire_acceptance','stream_acceptance','bridge_acceptance',
       'can_rx_acceptance','can_modes_tx_acceptance','lin_rx_acceptance','canfd_rx_acceptance',
       'flexray_rx_acceptance','advanced_tx_acceptance']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps',nargs='+',choices=STEPS,default=STEPS)
    parser.add_argument('--snapshot-only',action='store_true',help='Save a rebuildable source snapshot without opening USB/SWD')
    args=parser.parse_args()
    output=ROOT/'build/reports'/('suite-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True)
    source=output/'source';source.mkdir()
    sys.path.insert(0,str(ROOT/'tools'))
    from source_release import source_files
    for original in source_files():
        target=source/original.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target)
    manifest={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob('*') if p.is_file()}
    (output/'source-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if args.snapshot_only:
        print('Source snapshot (no board access):',source,flush=True);return
    report={'monitor_before':wait_monitor(), 'steps':[], 'overall':'IN_PROGRESS',
            'scope':'implemented teaching examples; NOT all 96 families or all master-plan gates',
            'manual_pending':['cold-power validation','external timing calibration','physical Safe strap']}
    def save():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    for step in args.steps:
        with (output/(step+'.log')).open('w') as log:
            process=subprocess.Popen([sys.executable,str(ROOT/'tests/hardware'/f'{step}.py')],
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            evidence=None
            for line in process.stdout:
                print(line,end='',flush=True);log.write(line);log.flush()
                if line.startswith('Evidence:'):evidence=line.split(':',1)[1].strip()
            code=process.wait()
        item={'step':step,'exit_code':code,'evidence':evidence}
        if evidence and (Path(evidence)/'report.json').exists():
            child=json.loads((Path(evidence)/'report.json').read_text())
            item['status']=child.get('automated_status','UNKNOWN')
        else:item['status']='FAIL'
        report['steps'].append(item);save()
        if code or item['status']!='PASS':
            report['overall']='NOT_PASSED';save()
            print('Suite stopped at failed/invalid step; investigate before rerun:',output,flush=True)
            raise SystemExit(1)
    report['monitor_after']=wait_monitor(True)
    report['overall']='PASS_IMPLEMENTED_SCOPE';save()
    print('Suite evidence:',output,flush=True)


if __name__=='__main__':main()
