# -*- makefile -*-
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

PREFIX = /usr/local
DESTDIR = /

PYTHON = python

all:

compile:
	$(PYTHON) -m compileall directory_bootstrap image_bootstrap

deb:
	debuild -uc -us --lintian-opts --display-info
	$(RM) -R build

dist:
	$(RM) MANIFEST
	./setup.py sdist

install:
	./setup.py install --prefix "$(PREFIX)" --root "$(DESTDIR)"

mrproper:
	git clean -d -f -x

.PHONY: all compile deb dist install mrproper
