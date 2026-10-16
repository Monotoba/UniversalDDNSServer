"""Peer authentication must be derived from the kernel, never JSON parameters."""
import socket
import sys
import unittest
from unittest.mock import patch

from universalddns.operator_peer import authenticated_operator_peer


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux SO_PEERCRED required")
class OperatorPeerTests(unittest.TestCase):
    def test_real_local_peer_identity_is_kernel_derived(self):
        import os
        import pwd

        first, second = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with patch("universalddns.operator_peer.pwd.getpwuid") as getuser, \
                 patch("universalddns.operator_peer.grp.getgrnam") as getgroup, \
                 patch("universalddns.operator_peer.os.getgrouplist") as groups:
                user = pwd.getpwuid(os.getuid())
                getuser.return_value = user
                getgroup.return_value = type("Group", (), {"gr_gid": 987})()
                groups.return_value = [user.pw_gid, 987]
                if os.getuid() == 0:
                    with self.assertRaises(PermissionError):
                        authenticated_operator_peer(first)
                else:
                    self.assertEqual(authenticated_operator_peer(first), user.pw_name)
        finally:
            first.close()
            second.close()

    def test_reject_missing_group(self):
        import os
        if os.getuid() == 0:
            self.skipTest("root is refused before group membership")
        first, second = socket.socketpair()
        try:
            with patch("universalddns.operator_peer.grp.getgrnam") as group, \
                 patch("universalddns.operator_peer.os.getgrouplist", return_value=[]):
                group.return_value = type("Group", (), {"gr_gid": 987})()
                with self.assertRaisesRegex(PermissionError, "not an authorized"):
                    authenticated_operator_peer(first)
        finally:
            first.close()
            second.close()

    def test_reject_tcp_socket(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            with self.assertRaises(PermissionError):
                authenticated_operator_peer(conn)


if __name__ == "__main__":
    unittest.main()
