KIKBOT_USERNAME ?= babebytes
KIKBOT_MACHINE := $(KIKBOT_USERNAME)-kikbot
# the password is the API key, which must be in $HOME/.netrc:
# machine babebytes-kikbot username babebytes password abcdef-012345
KIKBOT_API_KEY := $(shell awk '$$2 ~ /^$(KIKBOT_MACHINE)$$/ {print $$6}' \
	$(HOME)/.netrc)
SERVER_DOMAIN ?= myturn.mobi
KIKBOT_WEBHOOK := http://kikbot.$(SERVER_DOMAIN)/incoming
KIKBOT_PORT ?= 8088
VIRTUAL_ENV ?=  # this will be set only when `activate`d
SITES_AVAILABLE := /etc/nginx/sites-available
SITES_ENABLED := /etc/nginx/sites-enabled
APPS_AVAILABLE := /etc/uwsgi/apps-available
APPS_ENABLED := /etc/uwsgi/apps-enabled
export
# we test for virtualenv activation by looking for $(VIRTUAL_ENV)/bin/python,
# because since there is no /bin/python it will fail if deactivated

install: $(SITES_ENABLED)/kikbot.nginx $(APPS_ENABLED)/kikbot.ini
	sudo /etc/init.d/uwsgi restart
	sudo /etc/init.d/nginx restart

local_install:
	$(MAKE) SERVER_DOMAIN=local install

testrun: bot.py $(VIRTUAL_ENV)/bin/python
	python $<

uwsgi: bot.py
	sudo --preserve-env uwsgi \
	 --socket=/tmp/kikbot.sock \
	 --chmod-socket=666 \
	 --wsgi=bot:app \
	 --virtualenv=virtualenv

localtest:
	$(MAKE) SERVER_DOMAIN=local uwsgi

localfetch:
	wget --output-document=- --post-data=test http://kikbot.local/incoming

$(APPS_ENABLED)/kikbot.ini: $(APPS_AVAILABLE)/kikbot.ini
	sudo ln -sf $< $@

$(HOME)/.netrc:
	@echo See documentation for creating $(HOME)/.netrc

$(SITES_ENABLED)/kikbot.nginx: $(SITES_AVAILABLE)/kikbot.nginx
	sudo ln -sf $< $@

$(SITES_AVAILABLE)/% $(APPS_AVAILABLE)/%: % Makefile
	sudo rm -f $@  # in case it's a symlink from previous Makefile recipe
	@echo Rebuilding $@ with SERVER_DOMAIN=$(SERVER_DOMAIN)
	cat $< | sed -e 's%{KIKBOT_USERNAME}%$(KIKBOT_USERNAME)%' \
	 -e 's%{KIKBOT_API_KEY}%$(KIKBOT_API_KEY)%' \
	 -e 's%{KIKBOT_WEBHOOK}%$(KIKBOT_WEBHOOK)%' \
	 -e 's%{PWD}%$(PWD)%' \
	 | sudo tee $@

config: $(SITES_ENABLED)/kikbot.nginx virtualenv/lib/python2.7/site-packages/kik

virtualenv/lib/python2.7/site-packages/kik: $(VIRTUAL_ENV)/bin/python
	$(MAKE) dev_dependencies
	nosetests

lint: dev_dependencies
	flake8 .

virtualenv:
	virtualenv $@

devshell:
	$(MAKE) KIKBOT_USERNAME=pyturn shell

shell: virtualenv
	echo '***DO NOT*** use `deactivate`, instead simply ^D' >&2
	bash --rcfile $</bin/activate -i

appshell: $(VIRTUAL_ENV)/bin/python
	$< -i -c "from bot import *; import requests"

/bin/python:
	echo 'Must first `$(MAKE) shell`' >&2
	false

dev_dependencies: $(VIRTUAL_ENV)/bin/python
	pip install --upgrade --requirement requirements.dev.txt

dependencies: $(VIRTUAL_ENV)/bin/python
	pip install --upgrade --requirement requirements.txt

test: dependencies lint
	nosetests --with-coverage
set env:
	$@
.PHONY: test lint dependencies dist dev_dependencies
