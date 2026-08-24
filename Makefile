.PHONY: dist rpm clean

dist:
	python3 -m build --sdist --wheel

rpm:
	scripts/build-rpm.sh

clean:
	rm -rf build dist myprison.egg-info
