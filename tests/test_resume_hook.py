import os
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).resolve().parent.parent.joinpath('acer-wlan-resume').read_text()
with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    log = directory / 'calls'
    stub = directory / 'systemctl'
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_CALLS"\n')
    stub.chmod(0o755)
    hook = directory / 'hook'
    hook.write_text(source.replace('/usr/bin/systemctl', str(stub)))
    env = dict(os.environ, TEST_CALLS=str(log))
    subprocess.run(['/bin/sh', str(hook), 'pre', 'suspend'], env=env, check=True)
    assert not log.exists(), 'Recovery must not run before sleep.'
    subprocess.run(['/bin/sh', str(hook), 'post', 'suspend'], env=env, check=True)
    assert log.read_text() == '--no-block restart acer-wlan-enable.service\n'
print('Resume hook check passed: no action before sleep, asynchronous recovery after wake.')
