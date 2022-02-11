from concurrent.futures import ProcessPoolExecutor

import numpy as np
import torch

def tester(device):
    device = torch.device(device)

    while True:
        gpu_data = torch.ones((256, 512, 2096), device=device)
        gpu_op = torch.mvlgamma(torch.erfinv(gpu_data), 1)         # intense operation
        torch.cuda.empty_cache()

with ProcessPoolExecutor(max_workers=2) as executor:
    executor.map(tester, ['cuda:3', 'cuda:4'])