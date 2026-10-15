"""POSIX OS account attribution for local recovery proposal CLI."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from universalddns.local_operator import local_operator_identity


class OperatorIdentityTests(unittest.TestCase):
    def test_real_matching_non_root_uid(self):
        with (patch("universalddns.local_operator.os.name", "posix"),
              patch("universalddns.local_operator.os.getuid", return_value=1001),
              patch("universalddns.local_operator.os.geteuid", return_value=1001),
              patch("universalddns.local_operator.pwd.getpwuid",
                    return_value=SimpleNamespace(pw_name="test-operator", pw_gid=100)),
              patch("universalddns.local_operator.grp.getgrnam",
                    return_value=SimpleNamespace(gr_gid=201)),
              patch("universalddns.local_operator.os.getgrouplist",
                    return_value=[100, 201])):
            self.assertEqual(local_operator_identity(), "test-operator")

    def test_missing_operator_group_membership_is_refused(self):
        with (patch("universalddns.local_operator.os.name", "posix"),
              patch("universalddns.local_operator.os.getuid", return_value=1001),
              patch("universalddns.local_operator.os.geteuid", return_value=1001),
              patch("universalddns.local_operator.pwd.getpwuid",
                    return_value=SimpleNamespace(pw_name="ordinary", pw_gid=100)),
              patch("universalddns.local_operator.grp.getgrnam",
                    return_value=SimpleNamespace(gr_gid=201)),
              patch("universalddns.local_operator.os.getgrouplist",
                    return_value=[100])):
            with self.assertRaises(PermissionError):
                local_operator_identity()

    def test_root_and_uid_swap_are_refused(self):
        for real, effective in ((0, 0), (1001, 0), (0, 1001), (1001, 1002)):
            with self.subTest(real=real, effective=effective):
                with (patch("universalddns.local_operator.os.name", "posix"),
                      patch("universalddns.local_operator.os.getuid", return_value=real),
                      patch("universalddns.local_operator.os.geteuid", return_value=effective)):
                    with self.assertRaises(PermissionError):
                        local_operator_identity()

    def test_invalid_os_account_name_is_refused(self):
        with (patch("universalddns.local_operator.os.name", "posix"),
              patch("universalddns.local_operator.os.getuid", return_value=1001),
              patch("universalddns.local_operator.os.geteuid", return_value=1001),
              patch("universalddns.local_operator.pwd.getpwuid",
                    return_value=SimpleNamespace(pw_name="invalid account"))):
            with self.assertRaises(PermissionError):
                local_operator_identity()
