#!/usr/bin/env python3
import subprocess, time
def adb_cmd(args):
    return subprocess.run(['adb']+args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def device_connected():
    out = adb_cmd(['devices']).stdout
    for line in out.splitlines()[1:]:
        if '\tdevice' in line:
            return True
    return False

def wipe_device(factory_reset=True, dry_run=True):
    start = time.time()
    result = {'platform':'android','status':'FAILED'}
    if dry_run:
        result.update({'status':'DRY-RUN','note':'No destructive action performed'})
        return result
    if not device_connected():
        result.update({'status':'FAILED','error':'no adb device'})
        return result
    try:
        if factory_reset:
            r = adb_cmd(['shell','am','broadcast','-a','android.intent.action.MASTER_CLEAR'])
            result.update({'status':'SUCCESS','out': r.stdout or r.stderr})
        else:
            r = adb_cmd(['shell','rm','-rf','/sdcard/*'])
            result.update({'status':'SUCCESS','out': r.stdout or r.stderr})
    except Exception as e:
        result.update({'status':'FAILED','error':str(e)})
    result['duration_sec'] = round(time.time()-start,2)
    return result
