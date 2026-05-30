# Daneenon Body Tracking - Dockerfile
# Based on NVIDIA CUDA 

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Set Environment Variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Set work directory
WORKDIR /app

# Install dependencies
RUN apt update \
    && apt install software-properties-common -y \
    && add-apt-repository ppa:deadsnakes/ppa -y 
RUN apt update && apt install -y \
    python3.11 \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    git \
    wget \
    curl 
RUN apt-get clean 
RUN rm -rf /var/lib/apt/lists/* 
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1
RUN update-alternatives --auto python3


# Install Python libraries
RUN python3 -m pip install --upgrade pip
COPY requirements.txt .
RUN pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 --index-url https://download.pytorch.org/whl/cu118
# RUN pip install --no-cache-dir -r requirements.txt


# Expose ports
EXPOSE 8081 12345/udp

# Health Check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#     CMD curl -f http://localhost:8081/api/health || exit 1

# Start service
CMD ["/bin/bash"]
# CMD ["python3", "main.py"]

