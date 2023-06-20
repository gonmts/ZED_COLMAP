FROM colmap/colmap:latest

ARG UBUNTU_RELEASE_YEAR=18
ARG CUDA_MAJOR=11
ARG CUDA_MINOR=7
ARG ZED_SDK_MAJOR=3
ARG ZED_SDK_MINOR=8

ENV NVIDIA_DRIVER_CAPABILITIES \
    ${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}compute,video,utility

WORKDIR /home/zed_to_colmap


# Setup the ZED SDK
RUN apt-get update -y || true
RUN apt-get upgrade -y && apt-get autoremove -y && \
    apt-get install --no-install-recommends lsb-release wget less udev sudo zstd -y && \
    wget -q -O ZED_SDK_Linux_Ubuntu${UBUNTU_RELEASE_YEAR}.run https://download.stereolabs.com/zedsdk/${ZED_SDK_MAJOR}.${ZED_SDK_MINOR}/cu${CUDA_MAJOR}${CUDA_MINOR%.*}/ubuntu${UBUNTU_RELEASE_YEAR} && \
    chmod +x ZED_SDK_Linux_Ubuntu${UBUNTU_RELEASE_YEAR}.run ; ./ZED_SDK_Linux_Ubuntu${UBUNTU_RELEASE_YEAR}.run -- silent runtime_only && \
    rm ZED_SDK_Linux_Ubuntu${UBUNTU_RELEASE_YEAR}.run && \
    rm -rf /var/lib/apt/lists/*

# ZED Python API
RUN apt-get update -y || true
RUN apt-get install --no-install-recommends python3 python3-pip python-is-python3 libpng-dev libgomp1 -y && \
    # https://stackoverflow.com/a/63457606/7036639
    python3 -m pip install --upgrade pip && \
    wget download.stereolabs.com/zedsdk/pyzed -O /usr/local/zed/get_python_api.py && \
    python3 /usr/local/zed/get_python_api.py && \
    python3 -m pip install numpy opencv-python *.whl && \
    rm *.whl ; rm -rf /var/lib/apt/lists/*

COPY . .
RUN chmod +x zed_colmap_reconstruct.sh


