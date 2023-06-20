#!/bin/bash

set -e # Exit on the first error

die () {
    echo >&2 "$@"
    exit 1
}
[ "$#" -eq 2 ] || die "2 arguments required, $# provided. Please specify: 1) the path to the input .svo file and 2) the output path."


# The project folder must contain a folder "frames" with all the images.
SVO_FILE=$1
PROJECT_PATH=$2

exec > >(tee trace.log) 2>&1

# 0. Cleanup previous runs
rm -r -f frames/
mkdir frames
rm -f database.db
rm -f cameras.txt
rm -f images.txt
rm -f points3D.txt

# 1. Create cameras.txt, points3D.txt and images.txt with the relevant information,
# and extract frames from the ZED .svo file to frames/*.jpg files
echo [1/8] Extracting frames and camera poses from ZED svo file...
python3 zed_to_colmap.py -i -e "$SVO_FILE"
mkdir -p "$PROJECT_PATH/frames"
mv frames/*.jpg "$PROJECT_PATH/frames"
cp database.db "$PROJECT_PATH/database.db"
echo [1/8] Done with extraction of frames and camera poses from ZED svo file!

# 2. Feature extractor
echo [2/8] Running COLMAP feature extractor...
colmap feature_extractor \
    --database_path "$PROJECT_PATH/database.db" \
    --image_path "$PROJECT_PATH/frames"
echo [2/8] Done with COLMAP feature extractor!

# 3. Modify the database to include the manually set intrinsics and extrinsics.
echo [3/8] Modifying COLMAP database to include intrinsics and extrinsics from ZED...
cp $PROJECT_PATH/database.db database.db
python3 zed_to_colmap.py -i "$1"
python3 zed_to_colmap.py -e "$1"
cp database.db "$PROJECT_PATH/database.db"
echo [3/8] Done with modificaion of COLMAP database to include intrinsics and extrinsics from ZED!

# 4. Run the matcher.
echo [4/8] Running COLMAP sequential matcher...
# Option a: use exhaustive matcher
#colmap exhaustive_matcher \
#    --database_path $PROJECT_PATH/database.db
#
# Option b: use sequential matcher (for video sequences)
colmap sequential_matcher \
   --database_path "$PROJECT_PATH/database.db"
echo [4/8] Done with COLMAP sequential matcher!


# 5. Run point triangulator
echo [5/8] Running COLMAP point triangulator...
# First, create directories and copy the .txt files created in 1. into 'manual_sparse_model'.
mkdir -p "$PROJECT_PATH/sparse/manual_sparse_model"
cp cameras.txt "$PROJECT_PATH/sparse/manual_sparse_model/cameras.txt"
cp images.txt "$PROJECT_PATH/sparse/manual_sparse_model/images.txt"
cp points3D.txt "$PROJECT_PATH/sparse/manual_sparse_model/points3D.txt"
mkdir -p "$PROJECT_PATH/sparse/triangulated_sparse_model"
colmap point_triangulator \
    --database_path "$PROJECT_PATH/database.db" \
    --image_path "$PROJECT_PATH/frames" \
    --input_path "$PROJECT_PATH/sparse/manual_sparse_model" \
    --output_path "$PROJECT_PATH/sparse/triangulated_sparse_model"
echo [5/8] Done with COLMAP point triangulator!


# 6-8. Compute dense model from the parse model
echo [6/8] Running COLMAP image undistorter...
colmap image_undistorter \
    --image_path "$PROJECT_PATH/frames" \
    --input_path "$PROJECT_PATH/sparse/triangulated_sparse_model" \
    --output_path "$PROJECT_PATH/dense"
echo [6/8] Done with COLMAP image undistorter!

echo [7/8] Running COLMAP patch match stereo...
colmap patch_match_stereo \
    --workspace_path "$PROJECT_PATH/dense"
echo [7/8] Done with COLMAP patch match stereo!

echo [8/8] Running COLMAP stereo fusion...
colmap stereo_fusion \
    --workspace_path "$PROJECT_PATH/dense" \
    --output_path "$PROJECT_PATH/dense/fused.ply"
echo [8/8] Done with COLMAP stereo fusion!

cp trace.log "$PROJECT_PATH/trace.log"