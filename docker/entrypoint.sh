#!/bin/bash

set -Eeuo pipefail

declare -A MOUNTS

VOLUME_SPACE="/workspace"

MOUNTS["${ROOT}/models"]="${VOLUME_SPACE}/models"

MOUNTS["${ROOT}/embeddings"]="${VOLUME_SPACE}/embeddings"
MOUNTS["${ROOT}/extensions"]="${VOLUME_SPACE}/extensions"
MOUNTS["${ROOT}/scripts"]="${VOLUME_SPACE}/scripts"


for to_path in "${!MOUNTS[@]}"; do
  set -Eeuo pipefail
  from_path="${MOUNTS[${to_path}]}"
  rm -rf "${to_path}"
  if [ ! -f "$from_path" ]; then
    mkdir -vp "$from_path"
  fi
  mkdir -vp "$(dirname "${to_path}")"
  ln -sT "${from_path}" "${to_path}"
  echo Mounted $(basename "${from_path}")
done

git lfs install
python -m pip install rich
python -m pip install numexpr

if [ ! -f "${VOLUME_SPACE}/tmp/wsai.ready" ]; then
    rm -rf ${VOLUME_SPACE}/tmp/wsai
    git clone "https://huggingface.co/spaces/Moldwebs/wsai" ${VOLUME_SPACE}/tmp/wsai
    mv ${VOLUME_SPACE}/tmp/wsai/Lora/* ${VOLUME_SPACE}/models/Lora
    mv ${VOLUME_SPACE}/tmp/wsai/ControlNet/* ${VOLUME_SPACE}/models/ControlNet
    mv ${VOLUME_SPACE}/tmp/wsai/StableDiffusion/* ${VOLUME_SPACE}/models/Stable-diffusion
    mv ${VOLUME_SPACE}/tmp/wsai/embeddings/* ${VOLUME_SPACE}/embeddings
    touch ${VOLUME_SPACE}/tmp/wsai.ready
fi

exec "$@"
