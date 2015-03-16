# -*- makefile -*-
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

PREFIX = /usr/local
DESTDIR = /

all:

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

.PHONY: all deb dist install mrproper
