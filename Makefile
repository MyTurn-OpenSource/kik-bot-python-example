KIKBOT_USERNAME ?= babebytes
KIKBOT_MACHINE := $(KIKBOT_USERNAME)-kikbot
# the password is the API key, which must be in $HOME/.netrc:
# machine babebytes-kikbot username babebytes password abcdef-012345
KIKBOT_API_KEY := $(shell awk '$$2 ~ /^$(KIKBOT_MACHINE)$$/ {print $$6}' \
	$(HOME)/.netrc)
KIKBOT_WEBHOOK ?= http://jc.unternet.net/test.cgi
KIKBOT_PORT ?= 8088
VIRTUAL_ENV ?=  # this will be set only when `activate`d
SITES_AVAILABLE := /etc/nginx/sites-available
SITES_ENABLED := /etc/nginx/sites-enabled
export
# we test for virtualenv activation by looking for $(VIRTUAL_ENV)/bin/python,
# because since there is no /bin/python it will fail if deactivated

run: $(VIRTUAL_ENV)/bin/python $(SITES_ENABLED)/kikbot.nginx
	python bot.py

$(SITES_ENABLED)/kikbot.nginx: $(SITES_AVAILABLE)/kikbot.nginx
	sudo ln -sf $< $@
	sudo /etc/init.d/nginx restart

$(SITES_AVAILABLE)/kikbot.nginx: $(PWD)/kikbot.nginx
	sudo ln -sf $< $@

config: $(SITES_ENABLED)/kikbot.nginx

lint: dev_dependencies
	flake8 .

shell: env
	echo '***DO NOT*** use `deactivate`, instead simply ^D' >&2
	bash --rcfile $</bin/activate -i

/bin/python:
	echo 'Must first `$(MAKE) shell`' >&2
	false

dev_dependencies:
	pip install --upgrade --requirement requirements.dev.txt

dependencies:
	pip install --upgrade --requirement requirements.txt

test: dependencies lint
	nosetests --with-coverage
set:
	env
.PHONY: test lint dependencies dist dev_dependencies
