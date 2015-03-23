#! /bin/bash
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
echo "Called as:"
echo "  \$0 = \"$0"\"
echo "  \$@ = <$@>"
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
echo Environment:
env | sort
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
