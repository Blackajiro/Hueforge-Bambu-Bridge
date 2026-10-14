"""Watch one explicitly selected HueForge project; stdout is a JSON event stream."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import signal
import tempfile
import time

from hueforge_bambu import convert, read_template


def signature(path):
    if path is None:
        return None
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino)


def find_stl(hfp):
    matches = [p for p in hfp.parent.iterdir()
               if p.name.startswith(hfp.stem + '_Front_') and p.suffix.lower() == '.stl']
    if len(matches) > 1:
        raise ValueError('Multiple Front STL exports found. Keep one matching STL in the project folder.')
    return matches[0] if matches else None


class SaveTracker:
    def __init__(self, baseline):
        self.baseline = self.pending = baseline
        self.since = 0.0

    def ready(self, pair, now):
        if pair != self.pending:
            self.pending, self.since = pair, now
            return False
        # Both files must change; HFP may be written before or after the STL.
        return (now - self.since >= 3 and all(pair) and
                all(a != b for a, b in zip(pair, self.baseline)))

    def consume(self, pair):
        self.baseline = pair


def emit(kind, message, path=None):
    print(json.dumps(dict(event=kind, message=message, path=str(path) if path else None)), flush=True)


def watch(hfp, template):
    read_template(template)
    hfp = hfp.resolve(strict=True)
    if hfp.suffix.lower() != '.hfp':
        raise ValueError('Choose a HueForge .hfp project.')
    stl = find_stl(hfp)
    tracker = SaveTracker((signature(hfp), signature(stl)))
    emit('connected', 'Save the project in HueForge and confirm its save dialog. The next completed save will export automatically.')
    previous_message = None
    failed_pair = None
    while True:
        pair = None
        try:
            stl = find_stl(hfp)
            pair = (signature(hfp), signature(stl))
            if tracker.ready(pair, time.monotonic()) and pair != failed_pair:
                emit('converting', 'Creating a Bambu Studio project from your saved files…')
                with tempfile.TemporaryDirectory(prefix='hueforge-snapshot-') as folder:
                    folder = Path(folder)
                    source, mesh, output = folder/hfp.name, folder/stl.name, folder/'result.3mf'
                    shutil.copyfile(hfp, source)
                    shutil.copyfile(stl, mesh)
                    if pair != (signature(hfp), signature(find_stl(hfp))):
                        continue
                    # Keep converter diagnostics separate from the event stream.
                    import contextlib
                    import sys
                    with contextlib.redirect_stdout(sys.stderr):
                        convert(source, mesh, output, template)
                    if pair != (signature(hfp), signature(find_stl(hfp))):
                        continue
                    destination = hfp.parent/'Bambu Bridge Exports'
                    destination.mkdir(exist_ok=True)
                    target = destination/(hfp.stem + ' - ' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.3mf')
                    with target.open('xb') as result:
                        result.write(output.read_bytes())
                tracker.consume(pair)
                emit('ready', 'Export complete. Your next HueForge save will create a new version.', target)
                previous_message = None
            elif pair != tracker.baseline and pair != failed_pair:
                message = 'Waiting for HueForge to finish saving both the project and its STL…'
                if message != previous_message:
                    emit('waiting', message)
                    previous_message = message
        except Exception as error:
            message = str(error)
            if message != previous_message:
                emit('error', message + ' Fix the issue and save again in HueForge.')
                previous_message = message
            # Do not continuously repeat a failed conversion of the same saved pair.
            failed_pair = pair
        time.sleep(0.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hfp', type=Path)
    parser.add_argument('--template', type=Path, required=True)
    args = parser.parse_args()
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        watch(args.hfp, args.template)
    except Exception as error:
        emit('error', str(error))
        raise SystemExit(1)
