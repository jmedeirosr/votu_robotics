.PHONY: help validate test debug release bullseye user-installer nightly clean

PYTHON ?= python3

help:
	@echo "Votu FieldOps — sistema de build"
	@echo "  make validate  valida configuração e simula o pipeline"
	@echo "  make test      executa testes unitários e smoke tests"
	@echo "  make debug     gera release de depuração"
	@echo "  make release   gera .deb, instalador .run e metadados"
	@echo "  make bullseye  gera somente o .deb autocontido Bullseye ARM64"
	@echo "  make user-installer gera os Wizards .sh Bullseye ARM64 sem senha"
	@echo "  make nightly   gera release do canal nightly"
	@echo "  make clean     remove somente artefatos gerados"

validate:
	$(PYTHON) release.py --dry-run

test:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m py_compile src/*.py build.py release.py

debug:
	$(PYTHON) release.py --channel debug

release:
	$(PYTHON) release.py --channel release

bullseye:
	.venv/bin/python portable_release.py

user-installer: bullseye
	.venv/bin/python user_installer.py

nightly:
	$(PYTHON) release.py --channel nightly

clean:
	$(PYTHON) -c "import build; build.clean()"
