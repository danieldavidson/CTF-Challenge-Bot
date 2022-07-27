PWD = $(shell pwd)

build:
	docker build . -t ctfbot

image:
	docker images | grep ctfbot || docker build . -t ctfbot

lint: image
	docker run --rm -v ${PWD}/:/src/ ctfbot pylint **/*.py -E

checklint: image
	docker run --rm -v ${PWD}/:/src/ ctfbot pylint **/*.py --exit-zero

run: build
	docker run --rm -it ctfbot

runlocal: image
	docker run --rm -it -v ${PWD}/:/src/ ctfbot

test:
	docker run --rm -v ${PWD}/:/src/ ctfbot python3 runtests.py

background: image
	docker run --rm -d --name ctfbot ctfbot

stop:
	docker stop ctfbot
