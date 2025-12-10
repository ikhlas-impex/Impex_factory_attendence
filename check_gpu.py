from src.utils.gpu_utils import detect_gpu_capability

if __name__ == "__main__":
    gpu_enabled = detect_gpu_capability()
    if gpu_enabled:
        print("GPU is enabled.")
    else:
        print("GPU is not enabled.")