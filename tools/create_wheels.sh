OS_DIST=$(awk -F= '$1=="ID" { print $2 ;}' /etc/os-release)
pip wheel -r ../requirements.txt -w ../src/libs/$OS_DIST

blacklist=("hypothesis" "mock" "pytest")
for lib in $blacklist; do
  rm ../src/libs/$OS_DIST/*$lib*.whl
done