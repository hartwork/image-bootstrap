# -*- makefile -*-
# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

PREFIX = /usr/local
DESTDIR = /

PYTHON = python

all:

check:
	py.test --doctest-modules

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

isort:
	find -type f -name  '*.py' -print0 \
			| xargs --null isort \
				--project directory_bootstrap \
				--project image_bootstrap \
				--section-default THIRDPARTY \
				-m 4 --indent '        ' \
				--atomic

mrproper:
	git clean -d -f -x

.PHONY: all check compile deb dist install isort mrproper
