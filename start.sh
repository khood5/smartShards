# starts the node (must be run after setup)
export PYTHONPATH=$PYTHONPATH:$PWD
export FLASK_APP=$(pwd)/src/api
python3 src/api/__init__.py