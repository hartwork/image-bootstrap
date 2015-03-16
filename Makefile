PREFIX = /usr/local
DESTDIR = /

all:

deb:
	debuild -uc -us --lintian-opts --display-info

dist:
	$(RM) MANIFEST
	./setup.py sdist

install:
	./setup.py install --prefix "$(PREFIX)" --root "$(DESTDIR)"

mrproper:
	git clean -d -f -x

.PHONY: all deb dist install mrproper
