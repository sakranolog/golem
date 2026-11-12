#!/bin/bash
# Rebuild every asset from scratch. Usage: blender/build_all.sh [--fast]
set -e
cd "$(dirname "$0")"
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
FAST=$1
run() { echo "== $*"; "$B" -b --factory-startup -P "$@" > "logs/$(basename "$1" .py).log" 2>&1 || { tail -30 "logs/$(basename "$1" .py).log"; exit 1; }; }
mkdir -p logs previews textures
run build_golem.py -- $FAST
run build_props.py -- $FAST
run build_workshop.py -- $FAST
run bake_workshop.py -- $FAST
run render_env.py -- $FAST
run render_beauty.py -- $FAST
"$B" -b --factory-startup -P verify_glb.py -- golem > logs/verify_golem.log 2>&1
"$B" -b --factory-startup -P verify_glb.py -- props > logs/verify_props.log 2>&1
"$B" -b --factory-startup -P verify_glb.py -- workshop > logs/verify_workshop.log 2>&1
grep -h VERIFY logs/verify_*.log
python3 write_manifest.py
ls -la ../public/models ../public/env
