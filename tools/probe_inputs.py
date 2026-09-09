#!/usr/bin/env python3
"""Send explicit normal-button steps to existing local diagnostic hosts.

Each host records every request in its existing operations.jsonl. This helper
does not load states, write guest memory, or change the ROM. Example input:
  --inputs a:1,wait:120,right:24,wait:30 --name corridor-preview
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
import urllib.request

BUTTONS = {'a', 'b', 'start', 'select', 'l', 'r', 'up', 'down', 'left', 'right'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ports', type=int, nargs='+', required=True)
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if Path(args.name).name != args.name or not args.name:
        parser.error('Screenshot name must be a single filename stem')
    requests = []
    for step in args.inputs.split(','):
        key, count = step.strip().split(':')
        count = int(count)
        keys = key.split('+')
        if (key != 'wait' and (not set(keys) <= BUTTONS or len(set(keys)) != len(keys))) or not 1 <= count <= 3600:
            parser.error(f'Invalid button step: {step}')
        request = {'op': 'frames', 'count': count}
        if key != 'wait':
            request['buttons'] = keys
        requests.append(request)
    requests.append({'op': 'screenshot', 'name': args.name + '.png'})

    def run(port):
        for request in requests:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/', data=json.dumps(request).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.load(response)
            if not result.get('ok'):
                raise RuntimeError(f'Host {port}: {result}')
        return {'port': port, **result}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.ports)) as pool:
        for result in pool.map(run, args.ports):
            print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
