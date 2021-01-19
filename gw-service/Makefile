
REQUIREMENTS_FILE=../requirements-py3.txt
VENV_FOLDER=../gw_py3_venv

MAIN_PYTHON_FILE=../src/openmotics_service.py

OUTPUT_NAME=openmotics_service

SPEC_FILE=openmotics_service.spec


.PHONY: package run venv clean clean-venv
package: ${SPEC_FILE}
	. ./${VENV_FOLDER}/bin/activate; \
	pip list; \
	python --version; \
	pyinstaller \
		--onedir \
		${SPEC_FILE}
	cp -r dist-overlay/* dist/


esafe-package: package
	./create-package.sh

spec-file: ${SPEC_FILE}
${SPEC_FILE}:
	. ./${VENV_FOLDER}/bin/activate; \
	python --version; \
	pyi-makespec \
		--additional-hooks-dir=../hooks \
		--onedir \
		--add-data "../src/gateway/migrations:gateway/migrations" \
		--add-data "../src/gateway/webservice.py:gateway/webservice.py" \
		--add-data "../src/plugin_runtime:plugin_runtime" \
		--add-data "../src/plugins:plugins" \
		--add-data "../src/terms:terms" \
		--hidden-import cheroot.ssl \
		--hidden-import cheroot.ssl.builtin \
		--name ${OUTPUT_NAME} \
		${MAIN_PYTHON_FILE}

run:
	./dist/${OUTPUT_NAME}/${OUTPUT_NAME}

venv:
	pip install virtualenv; \
	python -m venv ${VENV_FOLDER}; \
	. ./${VENV_FOLDER}/bin/activate; \
	pip install -r ${REQUIREMENTS_FILE}; \
	pip install pyinstaller


clean:
	rm -rf __pycache__ build dist
	cd package; ./clean.sh

clean-spec:
	rm -rf ${SPEC_FILE}

clean-venv:
	rm -rf ${VENV_FOLDER}
