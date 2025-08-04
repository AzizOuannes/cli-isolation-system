# Stage 1: Base Image with ROS 2 Core
###########################################
FROM ubuntu:24.04 AS base
ENV DEBIAN_FRONTEND=noninteractive

# Install essential packages, locales, and timezone
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  locales \
  tzdata \
  curl \
  gnupg2 \
  lsb-release \
  sudo \
  && locale-gen en_US.UTF-8 \
  && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
  && ln -fs /usr/share/zoneinfo/UTC /etc/localtime \
  && dpkg-reconfigure --frontend noninteractive tzdata \
  && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8

# Install ROS 2 Jazzy
ENV ROS_DISTRO=jazzy
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null \
  && apt-get update && apt-get install -y --no-install-recommends \
  ros-jazzy-ros-base \
  python3-argcomplete \
  && rm -rf /var/lib/apt/lists/*

# Stage 2: Development Image
###########################################
FROM base AS dev

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  cmake \
  git \
  python3-pip \
  ros-dev-tools \
  nano \
  vim \
  wget \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user 'ros'
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN if getent passwd ubuntu > /dev/null 2>&1; then userdel -r ubuntu; fi && \
    groupadd --gid $USER_GID $USERNAME && \
    useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME && \
    echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

# Switch to the new user
USER $USERNAME
WORKDIR /home/$USERNAME

# Source ROS setup in .bashrc for convenience
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /home/$USERNAME/.bashrc \
  && echo "source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash" >> /home/$USERNAME/.bashrc

# Stage 3: Full Desktop Image (OPTIONAL - Commented out for faster builds)
###########################################
# FROM dev AS full
# 
# USER root
# # Install the full ROS 2 Desktop environment (includes RViz, etc.)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#   ros-jazzy-desktop \
#   && rm -rf /var/lib/apt/lists/*
# USER $USERNAME

# Stage 4: CLI Isolation Image (for ttyd integration)
###########################################
FROM dev AS cli-isolation

USER root

# Install ttyd
RUN wget https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64 -O /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd

# Create workspace directory accessible by ros user
RUN mkdir -p /workspace && chown $USERNAME:$USERNAME /workspace

# Add ROS2 environment to global profile so it's available for all shells
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /etc/bash.bashrc \
    && echo "source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash" >> /etc/bash.bashrc

# Switch back to ros user
USER $USERNAME
WORKDIR /workspace
EXPOSE 7681

CMD ["ttyd", "-W", "-p", "7681", "bash"]