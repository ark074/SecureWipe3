#!/usr/bin/env python3
"""Local BitShred Agent (safe stub)

- Polls cloud API for job status (requires API base and JWT token configured via env)
- Downloads job and would perform local wipe using tools/wipe_*.py (but defaults to dry-run)
- Reports back to server via /api/report

USAGE:
  export API_BASE=http://localhost:5001
  export AGENT_TOKEN=<JWT>
  python3 agents/agent.py --poll-interval 15
"""
import os, time, requests, argparse, json, subprocess
API_BASE = os.getenv('API_BASE','http://localhost:5001')
AGENT_TOKEN = os.getenv('AGENT_TOKEN','')
HEADERS = {'Authorization': f'Bearer {AGENT_TOKEN}', 'Content-Type':'application/json'}

def perform_local_action(job):
    # Safe: call wipe scripts in dry_run mode by default
    plat = (job.get('device') or {}).get('platform','linux').lower()
    params = job.get('params',{})
    params['dry_run'] = True if not params.get('confirm_local') else False
    if plat == 'windows':
        cmd = ['python3','tools/wipe_windows.py']
    elif plat == 'android':
        cmd = ['python3','tools/wipe_android.py']
    else:
        cmd = ['python3','tools/wipe_linux.py']
    # we call with json params via environment for simplicity (not destructive)
    env = os.environ.copy()
    env['WIPE_PARAMS'] = json.dumps(params)
    try:
        proc = subprocess.run(cmd + [], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True, timeout=600)
        out = proc.stdout + '\n' + proc.stderr
        status = 'success' if proc.returncode==0 else 'failed'
    except Exception as e:
        out = str(e); status='failed'
    return {'job_id': job.get('job_id'), 'status': 'dry-run', 'out': out}

def poll_loop(interval=15):
    print('Agent polling', API_BASE)
    while True:
        try:
            # This is a stub: in a real implementation agent would list assigned jobs or wait for webhook.
            time.sleep(interval)
        except KeyboardInterrupt:
            break

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--poll-interval', type=int, default=15)
    args = p.parse_args()
    poll_loop(args.poll_interval)
