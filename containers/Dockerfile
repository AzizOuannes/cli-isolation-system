FROM alpine:3.18

# Install required packages
RUN apk add --no-cache \
    bash \
    curl \
    wget \
    nano \
    vim \
    git \
    python3 \
    nodejs \
    npm \
    ttyd

# Create non-root user
RUN addgroup -g 1000 user && \
    adduser -D -s /bin/bash -G user -u 1000 user

# Create necessary directories with proper permissions
RUN mkdir -p /home/user && \
    chown -R user:user /home/user && \
    chmod 755 /home/user

# Set working directory
WORKDIR /home/user

# Switch to non-root user
USER user

# Expose ttyd port
EXPOSE 7681

# Default command
CMD ["ttyd", "-W", "-p", "7681", "bash"]