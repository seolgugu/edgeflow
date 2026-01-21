import subprocess
import os

def build_and_push(image_tag):
    # 임시 Dockerfile 생성
    dockerfile = """
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
# 프레임워크 자체도 설치 (개발 중엔 COPY로 대체 가능)
COPY . /app
RUN pip install .
"""
    import tempfile
    
    # 안전한 임시 파일 사용
    with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix='Dockerfile.edgeflow.') as f:
        f.write(dockerfile)
        temp_dockerfile_path = f.name

    try:
        # Build & Push
        subprocess.run([
        "docker", "buildx", "build",
        "--platform", "linux/amd64,linux/arm64", 
        "-f", temp_dockerfile_path,  # 임시 파일 경로 사용
        "-t", image_tag,
        "--push", 
        "."
    ], check=True)
    
    finally:
        # 빌드 후 임시 파일 정리
        if os.path.exists(temp_dockerfile_path):
            os.remove(temp_dockerfile_path)