"""Real kernel EMFILE behavior in a disposable RLIMIT_NOFILE subprocess."""
import os
import resource
import socket
import subprocess
import sys
import textwrap
import unittest

_CHILD = textwrap.dedent("""
    import array
    import errno
    import os
    import resource
    import socket
    import tempfile
    from pathlib import Path
    from universalddns.snapshot_handoff import receive_snapshot_fd

    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "snapshot"
        path.write_bytes(b"fixture")
        path.chmod(0o600)
        with socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM) as (tx, rx):
            original = os.open(path, os.O_RDONLY)
            try:
                tx.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                      array.array("i", [original]).tobytes())])
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                # Lower only this disposable process' soft limit.
                current = len(os.listdir("/proc/self/fd"))
                limit = max(current + 4, 32)
                if limit >= soft:
                    raise RuntimeError("insufficient RLIMIT headroom")
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
                extras = []
                while True:
                    try:
                        extras.append(os.open(os.devnull, os.O_RDONLY))
                    except OSError as exc:
                        if exc.errno != errno.EMFILE:
                            raise
                        break
                try:
                    try:
                        receive_snapshot_fd(
                            rx, authorized_uid=os.geteuid(),
                            producer_uid=os.geteuid())
                    except ValueError as exc:
                        if str(exc) != "handoff unavailable":
                            raise
                    else:
                        raise AssertionError("kernel EMFILE must fail closed")
                finally:
                    # Restore capacity before exercising a new transfer.
                    for fd in extras:
                        os.close(fd)
                tx.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                      array.array("i", [original]).tobytes())])
                recovered = receive_snapshot_fd(
                    rx, authorized_uid=os.geteuid(), producer_uid=os.geteuid())
                try:
                    assert os.read(recovered, 32) == b"fixture"
                finally:
                    os.close(recovered)
                print("PASS: kernel EMFILE rejected and later transfer recovered")
            finally:
                os.close(original)
""")


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "Linux RLIMIT_NOFILE and SCM_RIGHTS required")
class KernelDescriptorExhaustionTests(unittest.TestCase):
    def test_disposable_child_hits_emfile_and_recovers(self):
        completed = subprocess.run(
            [sys.executable, "-c", _CHILD], capture_output=True, text=True,
            timeout=15, check=False)
        self.assertEqual(
            completed.returncode, 0,
            f"child exit={completed.returncode}: {completed.stdout} {completed.stderr}")
        self.assertIn("PASS: kernel EMFILE rejected", completed.stdout)


if __name__ == "__main__":
    unittest.main()
