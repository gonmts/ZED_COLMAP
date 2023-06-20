# ZED to COLMAP utility

## Description 
This repo contains utility scripts to work with ZED stereoscopic cameras and COLMAP, in order to accelerate 3D reconstructions.

Essentially, this tool extracts frames from a ZED video (.svo file), camera intrinsics and extrinsics, and then initializes and runs COLMAP on this data.
The end result is a sparse and a dense 3D reconstruction, as usually returned by COLMAP.

The main advantages of using this tool are:

* **The sparse model creation is much faster**, because camera intrinsics and extrinsics are obtained from the ZED SDK in no time, and thus the COLMAP's bundle adjustment is very quick to converge;
* **The resulting models are in the correct (real-world) scale**, because the extrinsics injected into COLMAP, that came from the ZED SDK, were computed from stereo and thus are expressed in real-world dimensions;
* **The resolution of the dense model obtained through COLMAP is much higher than that obtained with ZEDfu**, because it is not limited in size;


## Requirements

In order to run this code, you need:

* An **NVIDIA GPU** -- _required by both the ZED SDK and COLMAP (for dense reconstruction)_;
* **Docker** installed in your machine;
* **NVIDIA container runtime** -- _since our docker container needs access to NVIDIA GPUs_;

For more information on how to install NVIDIA container runtime see [the official documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

The remaining dependencies (like the ZED SDK, COLMAP binaries and Python dependencies) are automatically handled by the docker image (see next section).
Unless you plan to run this tool outside docker, you don't have to install anything else in your host machine.

This was tested in a Linux environment. However, it might also run on other platforms, provided that you have docker and the NVIDIA container runtime properly configured in your platform.


## Building the docker image

The first time you use this tool, you need to compile its docker image by opening a terminal on the root of this repository and running:

```bash
docker build -t zed_colmap:1.0 .
```


## Using the tool

To use the tool to process a ZED video (.svo file), open a terminal on the root of this repository and run:

```bash
./run_in_docker.sh /path/to/your/video.svo /path/to/output
```

COLMAP outputs will be stored in the folder `/path/to/output` that you indicated. Note that this folder must exist and should be empty before running this tool.


## About

Developed by Gonçalo Matos in the context of his PhD at [SISCOG](https://www.siscog.pt/en-gb/), [Instituto Superior Técnico](https://tecnico.ulisboa.pt/en/) and [Institute for Systems and Robotics](https://welcome.isr.tecnico.ulisboa.pt/).
