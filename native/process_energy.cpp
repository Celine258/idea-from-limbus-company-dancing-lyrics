// Per-process WASAPI loopback; only scalar RMS leaves this process, never audio.
// API reference: Microsoft's ApplicationLoopback sample (Windows build 20348+).
#define NOMINMAX
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <wrl.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using Microsoft::WRL::ComPtr;
using Microsoft::WRL::RuntimeClass;
using Microsoft::WRL::RuntimeClassFlags;
using Microsoft::WRL::ClassicCom;
using Microsoft::WRL::FtmBase;

static void check(HRESULT result) { if (FAILED(result)) throw result; }

class Activation final : public RuntimeClass<RuntimeClassFlags<ClassicCom>, FtmBase,
    IActivateAudioInterfaceCompletionHandler> {
public:
    HANDLE done = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    HRESULT result = E_PENDING;
    ComPtr<IAudioClient> client;
    ~Activation() { if (done) CloseHandle(done); }
    STDMETHOD(ActivateCompleted)(IActivateAudioInterfaceAsyncOperation* operation) override {
        ComPtr<IUnknown> unknown;
        HRESULT activation = E_FAIL;
        result = operation->GetActivateResult(&activation, &unknown);
        if (SUCCEEDED(result)) result = activation;
        if (SUCCEEDED(result)) result = unknown.As(&client);
        SetEvent(done);
        return S_OK;
    }
};

int wmain(int argc, wchar_t** argv) {
    if (argc < 2) { std::cerr << "usage: ProcessEnergy.exe PID [seconds]\n"; return 2; }
    try {
        const DWORD pid = std::stoul(argv[1]);
        if (pid == 0) throw std::invalid_argument("PID must be positive");
        const double seconds = argc > 2 ? std::stod(argv[2]) : 24 * 3600;
        HANDLE target = OpenProcess(SYNCHRONIZE, FALSE, pid);
        if (!target) throw HRESULT_FROM_WIN32(GetLastError());
        check(CoInitializeEx(nullptr, COINIT_MULTITHREADED));
        auto activation = Microsoft::WRL::Make<Activation>();
        AUDIOCLIENT_ACTIVATION_PARAMS params{};
        params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
        params.ProcessLoopbackParams.TargetProcessId = pid;
        params.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;
        PROPVARIANT variant{};
        variant.vt = VT_BLOB;
        variant.blob.cbSize = sizeof(params);
        variant.blob.pBlobData = reinterpret_cast<BYTE*>(&params);
        ComPtr<IActivateAudioInterfaceAsyncOperation> operation;
        check(ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
            __uuidof(IAudioClient), &variant, activation.Get(), &operation));
        if (WaitForSingleObject(activation->done, 10000) != WAIT_OBJECT_0) throw HRESULT_FROM_WIN32(ERROR_TIMEOUT);
        check(activation->result);
        auto client = activation->client;
        WAVEFORMATEX format{};
        format.wFormatTag = WAVE_FORMAT_PCM;
        format.nChannels = 2;
        format.nSamplesPerSec = 44100;
        format.wBitsPerSample = 16;
        format.nBlockAlign = 4;
        format.nAvgBytesPerSec = format.nSamplesPerSec * format.nBlockAlign;
        check(client->Initialize(AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,
            0, 0, &format, nullptr));
        ComPtr<IAudioCaptureClient> capture;
        check(client->GetService(IID_PPV_ARGS(&capture)));
        HANDLE ready = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!ready) throw HRESULT_FROM_WIN32(GetLastError());
        check(client->SetEventHandle(ready));
        check(client->Start());
        const ULONGLONG started = GetTickCount64();
        ULONGLONG lastOutput = 0;
        while (GetTickCount64() - started < seconds * 1000 && WaitForSingleObject(target, 0) == WAIT_TIMEOUT) {
            WaitForSingleObject(ready, 100);
            UINT32 count = 0;
            double squareSum = 0;
            uint64_t samples = 0;
            check(capture->GetNextPacketSize(&count));
            while (count > 0) {
                BYTE* data = nullptr;
                DWORD flags = 0;
                check(capture->GetBuffer(&data, &count, &flags, nullptr, nullptr));
                const uint64_t length = static_cast<uint64_t>(count) * format.nChannels;
                if (!(flags & AUDCLNT_BUFFERFLAGS_SILENT) && data) {
                    const int16_t* pcm = reinterpret_cast<const int16_t*>(data);
                    for (uint64_t i = 0; i < length; i += 2) {
                        const double value = pcm[i] / 32768.0;
                        squareSum += value * value;
                    }
                }
                samples += (length + 1) / 2;
                check(capture->ReleaseBuffer(count));
                check(capture->GetNextPacketSize(&count));
            }
            if (GetTickCount64() - lastOutput >= 30) {
                const double level = samples ? std::min(1.0, std::sqrt(squareSum / samples) * 3.2) : 0;
                std::cout << "{\"level\":" << level << "}\n" << std::flush;
                lastOutput = GetTickCount64();
            }
        }
        client->Stop();
        CloseHandle(ready);
        CloseHandle(target);
        // COM objects leave scope before the process exits; audio is never written.
        return 0;
    } catch (HRESULT result) {
        std::cout << "{\"error\":\"WASAPI 0x" << std::hex << static_cast<unsigned long>(result) << "\"}\n";
    } catch (...) { std::cout << "{\"error\":\"Invalid capture parameters\"}\n"; }
    return 1;
}
