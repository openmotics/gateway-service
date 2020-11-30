REQUIREMENTS_FILE=requirements-py3.txt
VENV_FOLDER=gw_py3_venv


.PHONY: package run venv clean clean-venv
package:
	${make} -C vpn-service
	${make} -C gw-service




venv:
	pip install virtualenv; \
	python -m venv ${VENV_FOLDER}; \
	. ./${VENV_FOLDER}/bin/activate; \
	pip install -r ${REQUIREMENTS_FILE}; \
	pip install pyinstaller


clean:
	rm -rf __pycache__ build dist

clean-venv:
	rm -rf ${VENV_FOLDER}
