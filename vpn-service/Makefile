
REQUIREMENTS_FILE=../requirements-py3.txt
VENV_FOLDER=../gw_py3_venv

MAIN_PYTHON_FILE=../src/vpn_service.py

OUTPUT_NAME=vpn_service

SPEC_FILE=vpn_service.spec


.PHONY: package run venv clean clean-venv copy-overlay
package: ${SPEC_FILE}
	. ./${VENV_FOLDER}/bin/activate; \
	pip list; \
	python --version; \
	pyinstaller \
		--onedir \
		${SPEC_FILE}
	${MAKE} copy-overlay

copy-overlay:
	cp -r ./dist-overlay/* ./dist/


esafe-package:
	echo "not implemented"

version:
	. ./${VENV_FOLDER}/bin/activate; \
	pip list; \
	python --version;

${SPEC_FILE}:
	. ./${VENV_FOLDER}/bin/activate; \
	python --version; \
	pyi-makespec \
		--additional-hooks-dir=../hooks \
		--hidden-import=simplejson \
		--onedir \
		--name ${OUTPUT_NAME} \
		${MAIN_PYTHON_FILE}

run: copy-overlay
	./dist/${OUTPUT_NAME}/${OUTPUT_NAME}

venv:
	pip install virtualenv; \
	python -m venv ${VENV_FOLDER}; \
	. ./${VENV_FOLDER}/bin/activate; \
	pip install -r ${REQUIREMENTS_FILE}; \
	pip install pyinstaller

clean-all: clean clean-spec

clean:
	rm -rf __pycache__ build dist

clean-spec:
	rm -rf ${SPEC_FILE}

clean-venv:
	rm -rf ${VENV_FOLDER}
