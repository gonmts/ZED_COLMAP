import sqlite3.dbapi2
import argparse
import pyzed.sl as sl
import numpy as np
import shutil
from colmap.database import COLMAPDatabase, blob_to_array
from colmap.constants import CameraModel
from colmap.read_write_model import Camera, Image, CAMERA_MODEL_IDS, write_cameras_text, write_images_text, rotmat2qvec


def rotation_matrix_to_quaternions(m1):
    # get the real part of the quaternion first
    r = np.math.sqrt(float(1) + m1[0, 0] + m1[1, 1] + m1[2, 2]) * 0.5
    i = (m1[2, 1] - m1[1, 2]) / (4 * r)
    j = (m1[0, 2] - m1[2, 0]) / (4 * r)
    k = (m1[1, 0] - m1[0, 1]) / (4 * r)

    return np.asarray([r, i, j, k], dtype=np.float64)




def update_camera_extrinsics(frame_name: str, prior_q: np.array, prior_t: np.array,
                             database: sqlite3.dbapi2.Connection):
    """
    Updates the camera extrinsics for a given frame, in an existing database.
    :param frame_name: Name of the frame to update.
    :param prior_q: Rotation quaternion.
    :param prior_t: Translation vector.
    :param database: SQLite database.
    :return:
    """
    database.execute(
        "UPDATE images SET prior_qw=?, prior_qx=?, prior_qy=?, prior_qz=?, prior_tx=?, prior_ty=?, prior_tz=?  WHERE name=?",
        (prior_q[0], prior_q[1], prior_q[2],
         prior_q[3], prior_t[0], prior_t[1], prior_t[2], frame_name))



def convert_database_to_text_model(database:sqlite3.dbapi2.Connection):
    """
    Generates files cameras.txt, images.txt and points3D.txt from a COLMAP database.
    :param database: SQLite database.
    :return:
    """

    # Copy points3D.txt from the template
    shutil.copy("templates/points3D.txt", "points3D.txt")


    # Convert cameras
    cameras = {}
    rows = database.execute("SELECT * FROM cameras")
    rows = rows.fetchall()

    for row in rows:
        camera_id, model_id, width, height, params, prior = row
        params = blob_to_array(params, np.float64)

        camera = Camera(id=camera_id, model=CAMERA_MODEL_IDS[model_id].model_name,
               width=width, height=height,
               params=params)

        cameras[camera_id] = camera

    write_cameras_text(cameras, "cameras.txt")


    # Convert images
    images = {}
    rows = database.execute("SELECT * FROM images")
    rows = rows.fetchall()

    for row in rows:
        image_id, image_name, camera_id, prior_qw, prior_qx, prior_qy, prior_qz, prior_tx, prior_ty, prior_tz = row

        if prior_tz is None:
            prior_tz = 0  #FIXME ??

        qvec = np.array(tuple(map(float, [prior_qw, prior_qx, prior_qy, prior_qz])))
        tvec = np.array(tuple(map(float, [prior_tx, prior_ty, prior_tz])))

        image = Image(
                id=image_id, qvec=qvec, tvec=tvec,
                camera_id=camera_id, name=image_name,
                xys=np.array([]), point3D_ids=np.array([]))

        images[image_id] = image

    write_images_text(images, "images.txt")



def initialize_intrinsics_and_extrinsics(svo_path: str, use_viewer:bool = False):
    """
    Generates COLMAP database and txt files initialized with camera intrinsics
    and extrinsics, extracted from ZED SDK.
    :param svo_path: Path to the ZED video file (.svo).
    :return:
    """

    print("Running ZED to COLMAP conversion ... Press 'Esc' to quit")

    input_type = sl.InputType()
    input_type.set_from_svo_file(svo_path)
    init = sl.InitParameters(input_t=input_type,
                             svo_real_time_mode=False,
                             camera_resolution=sl.RESOLUTION.HD2K,
                             depth_mode=sl.DEPTH_MODE.ULTRA,  # sl.DEPTH_MODE.NEURAL,
                             coordinate_units=sl.UNIT.METER,
                             coordinate_system=sl.COORDINATE_SYSTEM.IMAGE, # equivalent to right-handed with Y down
                             depth_minimum_distance=0.15  # Set the minimum depth perception distance to 15cm
                             )

    runtime_parameters = sl.RuntimeParameters()
    runtime_parameters.sensing_mode = sl.SENSING_MODE.STANDARD  # Use STANDARD sensing mode
    # Setting the depth confidence parameters
    runtime_parameters.confidence_threshold = 100
    runtime_parameters.textureness_confidence_threshold = 100

    zed = sl.Camera()
    status = zed.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print(repr(status))
        exit()

    # Set output resolution
    res = zed.get_camera_information().camera_resolution  # Get configured camera resolution
    # res = sl.Resolution()
    # res.width = 720
    # res.height = 404

    # Set tracking parameters
    track_params = sl.PositionalTrackingParameters()
    # track_params.enable_spatial_memory = True

    # Enable positional tracking
    err = zed.enable_positional_tracking(track_params)

    camera_model = zed.get_camera_information().camera_model

    if use_viewer:
        # Create OpenGL viewer
        viewer = gl.GLViewer()
        viewer.init(1, [], camera_model, res)

    # Initialize COLMAP database
    db = COLMAPDatabase.connect("database.db")
    db.create_tables()

    # Copy points3D.txt from the template
    shutil.copy("templates/points3D.txt", "points3D.txt")

    # Fill cameras.txt file with intrinsics
    left_camera_parameters = zed.get_camera_information().calibration_parameters.left_cam
    distortion = left_camera_parameters.disto
    shutil.copy("templates/cameras.txt", "cameras.txt")
    with open("cameras.txt", mode="a") as cameras:
        cameras.write("1 RADIAL {0} {1} {2} {3} {4} {5} {6}".format(
            res.width,
            res.height,
            left_camera_parameters.fx,
            left_camera_parameters.cx,
            left_camera_parameters.cy,
            distortion[0],
            distortion[1]
        ))

    # Create camera in database
    camera_params = np.array(
        (left_camera_parameters.fx, left_camera_parameters.cx, left_camera_parameters.cy, distortion[0], distortion[1]))
    camera_id1 = db.add_camera(model=CameraModel.RADIAL.value,
                               width=res.width,
                               height=res.height,
                               params=camera_params)

    # Fill images.txt file with extrinsics
    shutil.copy("templates/images.txt", "images.txt")
    with open("images.txt", mode="a") as images:

        point_cloud = sl.Mat(res.width, res.height, sl.MAT_TYPE.F32_C4, sl.MEM.CPU)
        rgb_image = sl.Mat(res.width, res.height, sl.MAT_TYPE.U8_C3, sl.MEM.CPU)

        frame = 0
        while not use_viewer or viewer.is_available():
            if zed.grab() == sl.ERROR_CODE.SUCCESS:
                zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU, res)
                zed.retrieve_image(rgb_image)

                if use_viewer:
                    viewer.updateData(point_cloud)

                if frame > 0 and frame % 1 == 0:
                    zed_pose = sl.Pose()
                    state = zed.get_position(zed_pose, sl.REFERENCE_FRAME.WORLD)

                    rgb_image.write("frames/left_{0:04d}.jpg".format(frame), sl.MEM.CPU, 0)

                    # Create data for COLMAP
                    rotation_matrix = zed_pose.get_rotation_matrix().r.transpose()
                    translation = - rotation_matrix.dot(zed_pose.get_translation().get())
                    quaternion = rotation_matrix_to_quaternions(rotation_matrix)

                    # Create image in the database
                    image_id1 = db.add_image(name="left_{0:04d}.jpg".format(frame),
                                             camera_id=camera_id1,
                                             prior_q=quaternion,
                                             prior_t=translation)

                    images.write("{0} {1} {2} {3} {4} {5} {6} {7} {8} left_{9:04d}.jpg\n".format(
                        image_id1,  # frame id
                        quaternion[0],  # qw
                        quaternion[1],  # qx
                        quaternion[2],  # qy
                        quaternion[3],  # qz
                        translation[0],  # tx
                        translation[1],  # ty
                        translation[2],  # ty
                        camera_id1,  # camera id
                        frame  # frame number
                    ))
                    images.write("\n")  # Write a blank line for 2D points (no detections)

                frame += 1

            elif not use_viewer:
                break

    # Commit database to file
    db.commit()
    db.close()

    if use_viewer:
        viewer.exit()
    zed.close()



def initialize_intrinsics(svo_path: str):
    """
    Updates an existing COLMAP database with camera intrinsics extracted from ZED SDK,
    replacing the existing cameras by 1 single camera, and modifying all the images to
    use this same camera.
    :param svo_path: Path to the ZED video file (.svo).
    :return:
    """
    print("Running ZED to COLMAP conversion ... Press 'Esc' to quit")

    input_type = sl.InputType()
    input_type.set_from_svo_file(svo_path)
    init = sl.InitParameters(input_t=input_type,
                             svo_real_time_mode=False,
                             camera_resolution=sl.RESOLUTION.HD2K,
                             depth_mode=sl.DEPTH_MODE.ULTRA,  # sl.DEPTH_MODE.NEURAL,
                             coordinate_units=sl.UNIT.METER,
                             coordinate_system=sl.COORDINATE_SYSTEM.IMAGE,  # equivalent to right handed with Y down
                             depth_minimum_distance=0.15  # Set the minimum depth perception distance to 15cm
                             )

    runtime_parameters = sl.RuntimeParameters()
    runtime_parameters.sensing_mode = sl.SENSING_MODE.STANDARD  # Use STANDARD sensing mode
    # Setting the depth confidence parameters
    runtime_parameters.confidence_threshold = 100
    runtime_parameters.textureness_confidence_threshold = 100

    zed = sl.Camera()
    status = zed.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print(repr(status))
        exit()

    # Set output resolution
    res = zed.get_camera_information().camera_resolution  # Get configured camera resolution
    # res = sl.Resolution()
    # res.width = 720
    # res.height = 404

    # Set tracking parameters
    track_params = sl.PositionalTrackingParameters()
    # track_params.enable_spatial_memory = True

    # Enable positional tracking
    err = zed.enable_positional_tracking(track_params)

    camera_model = zed.get_camera_information().camera_model

    # Connect to COLMAP database
    db = COLMAPDatabase.connect("database.db")

    # Delete existing cameras in database
    db.execute("DELETE FROM cameras;")

    # Create new camera in database
    left_camera_parameters = zed.get_camera_information().calibration_parameters.left_cam
    distortion = left_camera_parameters.disto
    camera_params = np.array((left_camera_parameters.fx, left_camera_parameters.cx, left_camera_parameters.cy, distortion[0], distortion[1]))
    camera_id1 = db.add_camera(model=CameraModel.RADIAL.value,
                               width=res.width,
                               height=res.height,
                               params=camera_params)

    # Update images to point to new camera
    db.execute("UPDATE images SET camera_id=?", (camera_id1,))

    # Commit database to file
    db.commit()
    db.close()

    zed.close()



def initialize_extrinsics(svo_path: str, use_viewer:bool = False):
    """
    Updates an existing COLMAP database with camera extrinsics extracted from ZED SDK.
    Cameras and their intrinsics are left untouched.
    :param svo_path: Path to the ZED video file (.svo).
    :return:
    """

    print("Running ZED to COLMAP conversion ... Press 'Esc' to quit")

    input_type = sl.InputType()
    input_type.set_from_svo_file(svo_path)
    init = sl.InitParameters(input_t=input_type,
                             svo_real_time_mode=False,
                             camera_resolution=sl.RESOLUTION.HD2K,
                             depth_mode=sl.DEPTH_MODE.ULTRA,  # sl.DEPTH_MODE.NEURAL,
                             coordinate_units=sl.UNIT.METER,
                             coordinate_system=sl.COORDINATE_SYSTEM.IMAGE, # equivalent to right handed with Y down
                             depth_minimum_distance=0.15  # Set the minimum depth perception distance to 15cm
                             )

    runtime_parameters = sl.RuntimeParameters()
    runtime_parameters.sensing_mode = sl.SENSING_MODE.STANDARD  # Use STANDARD sensing mode
    # Setting the depth confidence parameters
    runtime_parameters.confidence_threshold = 100
    runtime_parameters.textureness_confidence_threshold = 100

    zed = sl.Camera()
    status = zed.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print(repr(status))
        exit()

    # Set output resolution
    res = zed.get_camera_information().camera_resolution  # Get configured camera resolution
    # res = sl.Resolution()
    # res.width = 720
    # res.height = 404

    # Set tracking parameters
    track_params = sl.PositionalTrackingParameters()
    # track_params.enable_spatial_memory = True

    # Enable positional tracking
    err = zed.enable_positional_tracking(track_params)

    camera_model = zed.get_camera_information().camera_model

    if use_viewer:
        # Create OpenGL viewer
        viewer = gl.GLViewer()
        viewer.init(1, [], camera_model, res)


    # Connect to COLMAP database
    db = COLMAPDatabase.connect("database.db")


    # Fill database with extrinsics

    point_cloud = sl.Mat(res.width, res.height, sl.MAT_TYPE.F32_C4, sl.MEM.CPU)
    rgb_image = sl.Mat(res.width, res.height, sl.MAT_TYPE.U8_C3, sl.MEM.CPU)

    frame = 0
    while not use_viewer or viewer.is_available():
        if zed.grab() == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU, res)
            zed.retrieve_image(rgb_image)

            if use_viewer:
                viewer.updateData(point_cloud)

            zed_pose = sl.Pose()
            state = zed.get_position(zed_pose, sl.REFERENCE_FRAME.WORLD)

            # Create data for COLMAP
            rotation_matrix = zed_pose.get_rotation_matrix().r.transpose()
            translation = - rotation_matrix.dot(zed_pose.get_translation().get())
            quaternion = rotation_matrix_to_quaternions(rotation_matrix)

            # Update image extrinsics in the database
            update_camera_extrinsics(frame_name="left_{0:04d}.jpg".format(frame), prior_q=quaternion, prior_t=translation, database=db)

            frame += 1

        elif not use_viewer:
            break

    # Commit database to file
    db.commit()
    db.close()

    if use_viewer:
        viewer.exit()
    zed.close()



if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog='zed_to_colmap.py',
        description='Reads intrinsics and extrinsics from a ZED video file and writes them in the format required by COLMAP.',
        epilog='')

    parser.add_argument('filename')  # positional argument
    parser.add_argument('-i', '--intrinsics', action='store_true', help='Initialize COLMAP intrinsics')
    parser.add_argument('-e', '--extrinsics', action='store_true', help='Initialize COLMAP extrinsics')
    parser.add_argument('-t', '--text_model', action='store_true', help='Convert COLMAP database to text model (cameras.txt, images.txt, points3D.txt)')
    parser.add_argument('-v', '--viewer', action='store_true', help='Show 3D point cloud in realtime while reading frames')
    args = parser.parse_args()

    if args.viewer:
        import ogl_viewer.viewer as gl
        use_viewer = True
    else:
        use_viewer = False

    if not args.intrinsics and not args.extrinsics and not args.text_model:
        print("Nothing to do. Please specify at least one of the options -i or -e or -t.")
        exit()

    filename = args.filename
    print("Reading SVO file: {0}".format(filename))

    if args.intrinsics and args.extrinsics:
        print("Initializing COLMAP intrinsics and extrinsics")
        initialize_intrinsics_and_extrinsics(filename, use_viewer)

    elif args.extrinsics:
        initialize_extrinsics(filename, use_viewer)

    elif args.intrinsics:
        initialize_intrinsics(filename)

    elif args.text_model:
        db = COLMAPDatabase.connect("database.db")
        convert_database_to_text_model(db)

    else:
        print("No option selected. Exiting.")
        exit()
