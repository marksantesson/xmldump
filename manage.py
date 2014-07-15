#!/usr/bin/env python

#
# This test project is set up with an adminstrator account. Username
# is "admin" and password is "password".
#

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangotest.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

