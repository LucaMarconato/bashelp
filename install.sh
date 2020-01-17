#!/bin/bash

function CheckCommand() {
	type $1 >/dev/null 2>&1 || { echo >&2 "It's required $1 but it's not installed.  Aborting."; exit 1; }
}

# CheckCommand 'pandoc'
CheckCommand 'sqlite3'
CheckCommand 'python3'
CheckCommand 'nano'

# cp bashelp.py /usr/local/bin/bashelp
echo "alias bh=\"python $(pwd)/bashelp.py\"" >> ~/.bash_profile

## pandoc -s -w man docs/manpage.md -o docs/bashelp.1
#mkdir -p /usr/local/man/man1
#mv docs/bashelp.1 /usr/local/man/man1/bashelp.1.gz
#
#echo 'bashelp has been succesfully installed'
