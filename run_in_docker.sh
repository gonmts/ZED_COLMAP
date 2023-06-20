#!/bin/bash

die () {
    echo >&2 "$@"
    exit 1
}
[ "$#" -eq 2 ] || die "2 arguments required, $# provided. Please specify: 1) the path to the input .svo file and 2) the output path."

SVO_FILE=$1
OUTPUT_PATH=$2

# Automatic reconstruction
docker run --gpus all --rm -it -v "$SVO_FILE:/home/input/video.svo" -v "$OUTPUT_PATH":/home/output zed_colmap:1.0 ./zed_colmap_reconstruct.sh /home/input/video.svo /home/output

# Interactive shell
#docker run --gpus all --rm -it -v "$SVO_FILE:/home/input/video.svo" -v "$OUTPUT_PATH":/home/output zed_colmap:1.0 /bin/bash
