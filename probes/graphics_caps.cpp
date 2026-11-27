// SPDX-License-Identifier: GPL-3.0-or-later
// Query graphics capabilities without loading a title or printing adapter IDs.
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <cstdio>
using Microsoft::WRL::ComPtr;
int main() {
    ComPtr<IDXGIFactory6> factory;
    HRESULT hr = CreateDXGIFactory2(0, IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        std::printf("DXGI factory failed: 0x%08lx\n", static_cast<unsigned long>(hr));
        return 2;
    }
    ComPtr<ID3D12Device> device;
    for (UINT i = 0;; ++i) {
        ComPtr<IDXGIAdapter1> adapter;
        hr = factory->EnumAdapterByGpuPreference(i, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                                IID_PPV_ARGS(&adapter));
        if (hr == DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(hr)) break;
        DXGI_ADAPTER_DESC1 desc{};
        if (FAILED(adapter->GetDesc1(&desc)) || (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE)) continue;
        if (SUCCEEDED(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0,
                                       IID_PPV_ARGS(&device)))) break;
    }
    if (!device) {
        std::puts("No hardware D3D12 device available");
        return 3;
    }
    D3D12_FEATURE_DATA_SHADER_MODEL model{D3D_SHADER_MODEL_6_6};
    const bool sm = SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_SHADER_MODEL, &model, sizeof(model)))
                    && model.HighestShaderModel >= D3D_SHADER_MODEL_6_6;
    D3D12_FEATURE_DATA_D3D12_OPTIONS7 opt7{};
    const bool mesh = SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS7, &opt7, sizeof(opt7)))
                      && opt7.MeshShaderTier != D3D12_MESH_SHADER_TIER_NOT_SUPPORTED;
    D3D12_FEATURE_DATA_D3D12_OPTIONS1 opt1{};
    const bool wave = SUCCEEDED(device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS1, &opt1, sizeof(opt1)))
                      && opt1.WaveOps;
    std::printf("Shader Model 6.6: %s\nMesh shaders: %s\nWave operations: %s\n",
                sm ? "yes" : "no", mesh ? "yes" : "no", wave ? "yes" : "no");
    if (wave) std::printf("Wave lanes: %u-%u\n", opt1.WaveLaneCountMin, opt1.WaveLaneCountMax);
    return sm && mesh && wave ? 0 : 4;
}
