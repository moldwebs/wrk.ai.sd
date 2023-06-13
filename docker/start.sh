#!/bin/bash

echo "Worker Initiated"

echo "Starting WebUI API"
# python /stable-diffusion-webui/webui.py --skip-python-version-check --skip-torch-cuda-test --no-tests --skip-install --lowram --opt-sdp-attention --disable-safe-unpickle --port 3000 --api --nowebui --skip-version-check  --no-hashing --no-download-sd-model &
python -u webui.py --listen --port 3000 --allow-code --xformers --enable-insecure-extension-access --disable-safe-unpickle --api --skip-python-version-check --skip-torch-cuda-test --skip-version-check
# python webui.py --port 3000 --allow-code --xformers --enable-insecure-extension-access --disable-safe-unpickle --api --nowebui --skip-python-version-check --skip-torch-cuda-test --skip-version-check &

# echo "Starting RunPod Handler"
# python -u /docker/rp_handler.py
