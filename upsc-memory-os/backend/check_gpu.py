"""Check GPU availability in the current Python environment."""
import torch
import onnxruntime as ort
from sentence_transformers import SentenceTransformer

print("\n" + "=" * 50)
print("  GPU DIAGNOSTICS")
print("=" * 50)
print(f"PyTorch version:      {torch.__version__}")
print(f"CUDA available:       {torch.cuda.is_available()}")
print(f"CUDA build version:   {torch.version.cuda}")
if torch.cuda.is_available():
    print(f"GPU device:           {torch.cuda.get_device_name(0)}")
    print(f"GPU memory (total):   {round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)} GB")
else:
    print("GPU device:           NONE — CPU only!")

print(f"\nONNX Runtime version: {ort.__version__}")
print(f"ONNX providers:       {ort.get_available_providers()}")
onnx_gpu = "CUDAExecutionProvider" in ort.get_available_providers()
print(f"ONNX GPU support:     {onnx_gpu}")

print("\n--- Loading SentenceTransformer ---")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("BAAI/bge-base-en-v1.5", device=device)
print(f"Model loaded on:      {model.device}")

# Quick encode test
v = model.encode("Test sentence for GPU verification")
if torch.cuda.is_available():
    print(f"GPU memory used:      {round(torch.cuda.memory_allocated(0) / 1024**2, 1)} MB")

print("=" * 50 + "\n")
