"""Watch one explicitly selected HueForge project; stdout is a JSON event stream."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import signal
import tempfile
import time

from hueforge_bambu import convert


def signature(path):
    if path is None:
        return None
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino)


def find_stl(hfp):
    matches = [p for p in hfp.parent.iterdir()
               if p.name.startswith(hfp.stem + '_Front_') and p.suffix.lower() == '.stl']
    if len(matches) > 1:
        raise ValueError('Più STL Front per questo progetto. Salva in una cartella dedicata.')
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


def watch(hfp):
    hfp = hfp.resolve(strict=True)
    if hfp.suffix.lower() != '.hfp':
        raise ValueError('Seleziona un progetto .hfp')
    stl = find_stl(hfp)
    tracker = SaveTracker((signature(hfp), signature(stl)))
    emit('waiting', 'Collegato. Salva il progetto in HueForge per esportare.')
    previous_message = None
    failed_pair = None
    while True:
        pair = None
        try:
            stl = find_stl(hfp)
            pair = (signature(hfp), signature(stl))
            if tracker.ready(pair, time.monotonic()) and pair != failed_pair:
                emit('converting', 'Salvataggio rilevato. Creo il progetto per Bambu Studio…')
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
                        convert(source, mesh, output)
                    if pair != (signature(hfp), signature(find_stl(hfp))):
                        continue
                    destination = hfp.parent/'Bambu Bridge Exports'
                    destination.mkdir(exist_ok=True)
                    target = destination/(hfp.stem + ' - ' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.3mf')
                    with target.open('xb') as result:
                        result.write(output.read_bytes())
                tracker.consume(pair)
                emit('ready', '3MF pronto. Puoi continuare a lavorare in HueForge.', target)
                previous_message = None
            elif pair != tracker.baseline and pair != failed_pair:
                message = 'Attendo che HueForge completi il salvataggio di HFP e STL…'
                if message != previous_message:
                    emit('waiting', message)
                    previous_message = message
        except Exception as error:
            message = str(error)
            if message != previous_message:
                emit('error', message + ' Correggi e salva di nuovo in HueForge.')
                previous_message = message
            # Do not continuously repeat a failed conversion of the same saved pair.
            failed_pair = pair
        time.sleep(0.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hfp', type=Path)
    args = parser.parse_args()
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        watch(args.hfp)
    except Exception as error:
        emit('error', str(error))
        raise SystemExit(1)
