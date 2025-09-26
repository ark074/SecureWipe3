#!/usr/bin/env python3
import subprocess, time, json, os
def wipe_device(device='/dev/sdX', passes=1, dry_run=True):
    start = time.time()
    result = {'platform':'linux','device':device,'passes':passes,'status':'FAILED'}
    if dry_run:
        result.update({'status':'DRY-RUN','note':'No destructive action performed'})
        return result
    try:
        cmd = ['shred','-v','-n',str(passes),device]
        subprocess.run(cmd, check=True)
        result.update({'status':'SUCCESS','duration_sec': round(time.time()-start,2)})
    except Exception as e:
        result.update({'status':'FAILED','error':str(e)})
    return result
