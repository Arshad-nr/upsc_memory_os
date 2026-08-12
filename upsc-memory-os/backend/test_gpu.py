import torch
import onnxruntime as ort

print('\n--- GPU DIAGNOSTICS ---')
print('PyTorch sees GPU:', torch.cuda.is_available())
print('ONNX FastEmbed sees GPU:', 'CUDAExecutionProvider' in ort.get_available_providers())
print('Providers:', ort.get_available_providers())
print('-----------------------\n')
