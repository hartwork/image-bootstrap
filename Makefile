PREFIX = /usr/local
DESTDIR = /

all:

dist:
	$(RM) MANIFEST
	./setup.py sdist

install:
	./setup.py install --prefix "$(PREFIX)" --root "$(DESTDIR)"

.PHONY: all dist install
