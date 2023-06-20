from enum import Enum


class CameraModel(Enum):
    """
    COLMAP camera model constants.
    See https://github.com/colmap/colmap/blob/master/src/base/camera_models.h
    """
    SIMPLE_PINHOLE = 0
    PINHOLE = 1
    SIMPLE_RADIAL = 2
    RADIAL = 3
    OPENCV = 4
    OPENCV_FISHEYE = 5
    FULL_OPENCV = 6
    FOV = 7
    SIMPLE_RADIAL_FISHEYE = 8
    RADIAL_FISHEYE = 9
    THIN_PRISM_FISHEYE = 10