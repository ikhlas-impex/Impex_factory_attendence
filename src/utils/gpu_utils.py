"""Utilities for detecting GPU capabilities."""


def detect_gpu_capability():
    """Detect whether a CUDA‑capable GPU is available.

    The function checks for GPU support using commonly available libraries.
    It first attempts to query the providers available to ``onnxruntime`` and
    then falls back to checking ``torch.cuda``. Any import errors or runtime
    issues are swallowed so that the function safely returns ``False`` when GPU
    support cannot be determined.

    Returns:
        bool: ``True`` if a CUDA execution provider or CUDA‑enabled Torch
        runtime is available, otherwise ``False``.
    """

    # Check ONNX Runtime for CUDA-capable providers
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            return True
    except Exception:
        # onnxruntime is not installed or failed to query providers
        pass

    # Fallback to PyTorch CUDA detection
    try:
        import torch

        if torch.cuda.is_available():
            return True
    except Exception:
        # torch is not installed or CUDA query failed
        pass

    return False
