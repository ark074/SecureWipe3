#!/usr/bin/env python3
import subprocess, time, os
def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def wipe_device(drive='C', mode='free_space', dry_run=True):
    start = time.time()
    result = {'platform':'windows','drive':drive,'mode':mode,'status':'FAILED'}
    if dry_run:
        result.update({'status':'DRY-RUN','note':'No destructive action performed'})
        return result
    try:
        if mode == 'free_space':
            subprocess.run(['cipher','/w:{}\\'.format(drive)], check=True)
            result.update({'status':'SUCCESS'})
        else:
            if not is_admin():
                raise PermissionError('Admin required for full wipe')
            script = 'select disk 0\nclean all\nexit\n'
            with open('diskpart_script.txt','w') as f:
                f.write(script)
            subprocess.run(['diskpart','/s','diskpart_script.txt'], check=True)
            os.remove('diskpart_script.txt')
            result.update({'status':'SUCCESS'})
    except Exception as e:
        result.update({'status':'FAILED','error':str(e)})
    result['duration_sec'] = round(time.time()-start,2)
    return result
