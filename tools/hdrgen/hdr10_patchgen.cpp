// HDR10 patch generator: a borderless full-screen D3D11 window whose swapchain is R10G10B10A2 tagged
// DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020, so the PQ code values written are what the display receives
// (no SDR-to-HDR mapping, no SDR white level). Driven over stdin, one command per line:
//   N <nits> [area]   centred grey patch at <nits> (ST 2084), area = share of the screen (default 0.1)
//   P <code> [area]   same with a normalized PQ code value 0..1
//   C <r> <g> <b> [area]  patch with separate 10-bit PQ codes per channel (0..1023), for white balance
//   B <nits>          background level (default 0 = black)
//   Q                 quit
// Replies on stdout: "READY ..." at start (or "ERROR ..." and exit), then "OK <pq code> <10-bit code>" (for C:
// "OK <r> <g> <b>", the 10-bit codes drawn) once a command's frame has been presented and held for a few vsyncs.
// Esc closes the window.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11_1.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <mutex>
#include <string>
#include <sstream>
#include <thread>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

using Microsoft::WRL::ComPtr;

static double PqFromNits(double nits) {
    const double m1 = 0.1593017578125, m2 = 78.84375, c1 = 0.8359375, c2 = 18.8515625, c3 = 18.6875;
    double y = std::max(nits, 0.0) / 10000.0;
    double yp = std::pow(y, m1);
    return std::pow((c1 + c2 * yp) / (1.0 + c3 * yp), m2);
}

struct Command {
    char op = 0;
    double value = 0, area = 0.1;
    double rgb[3] = {0, 0, 0};  // C: 10-bit codes per channel
    long id = 0;
};

static std::mutex g_lock;
static Command g_pending;
static std::atomic<bool> g_quit{false};

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == WM_KEYDOWN && w == VK_ESCAPE) { g_quit = true; return 0; }
    if (m == WM_SETCURSOR) { SetCursor(nullptr); return TRUE; }
    if (m == WM_DESTROY) { g_quit = true; PostQuitMessage(0); return 0; }
    return DefWindowProcW(h, m, w, l);
}

static void Reader() {
    std::string line;
    long id = 0;
    while (!g_quit && std::getline(std::cin, line)) {
        std::istringstream ss(line);
        Command c;
        ss >> c.op;
        if (!c.op) continue;
        c.op = (char)toupper(c.op);
        if (c.op == 'Q') break;
        if (c.op == 'C') ss >> c.rgb[0] >> c.rgb[1] >> c.rgb[2];
        else ss >> c.value;
        if (!(ss >> c.area)) c.area = 0.1;
        c.id = ++id;
        std::lock_guard<std::mutex> g(g_lock);
        g_pending = c;
    }
    g_quit = true;
}

static int Fail(const char* what, HRESULT hr) {
    printf("ERROR %s (hr=0x%08lX)\n", what, (unsigned long)hr);
    fflush(stdout);
    return 1;
}

int main(int argc, char** argv) {
    // --composed: leave the window 2 px short of full screen, so DWM composes it (no independent flip).
    bool composed = argc > 1 && std::string(argv[1]) == "--composed";
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    // Keep the display on while patches are shown (the display-off timer only resets on user input).
    SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED);

    // Primary monitor (the AW3225QF is the only display here); full screen, borderless, topmost.
    HMONITOR mon = MonitorFromPoint(POINT{0, 0}, MONITOR_DEFAULTTOPRIMARY);
    MONITORINFO mi{sizeof(mi)};
    GetMonitorInfoW(mon, &mi);
    const int W = mi.rcMonitor.right - mi.rcMonitor.left;
    const int H = mi.rcMonitor.bottom - mi.rcMonitor.top - (composed ? 2 : 0);

    WNDCLASSW wc{};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.lpszClassName = L"HDR10PatchGen";
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    RegisterClassW(&wc);
    HWND hwnd = CreateWindowExW(WS_EX_TOPMOST, wc.lpszClassName, L"HDR10 patch generator", WS_POPUP | WS_VISIBLE,
                                mi.rcMonitor.left, mi.rcMonitor.top, W, H, nullptr, nullptr, wc.hInstance, nullptr);
    if (!hwnd) return Fail("CreateWindow", HRESULT_FROM_WIN32(GetLastError()));

    ComPtr<ID3D11Device> dev;
    ComPtr<ID3D11DeviceContext> ctx0;
    HRESULT hr = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr,
                                   0, D3D11_SDK_VERSION, &dev, nullptr, &ctx0);
    if (FAILED(hr)) return Fail("D3D11CreateDevice", hr);
    ComPtr<ID3D11DeviceContext1> ctx;
    ctx0.As(&ctx);

    ComPtr<IDXGIDevice> dxgiDev;
    dev.As(&dxgiDev);
    ComPtr<IDXGIAdapter> adapter;
    dxgiDev->GetAdapter(&adapter);
    ComPtr<IDXGIFactory2> factory;
    adapter->GetParent(IID_PPV_ARGS(&factory));

    DXGI_SWAP_CHAIN_DESC1 sd{};
    sd.Width = W;
    sd.Height = H;
    sd.Format = DXGI_FORMAT_R10G10B10A2_UNORM;
    sd.SampleDesc.Count = 1;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.BufferCount = 2;
    sd.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    sd.AlphaMode = DXGI_ALPHA_MODE_IGNORE;
    ComPtr<IDXGISwapChain1> sc1;
    hr = factory->CreateSwapChainForHwnd(dev.Get(), hwnd, &sd, nullptr, nullptr, &sc1);
    if (FAILED(hr)) return Fail("CreateSwapChainForHwnd", hr);
    factory->MakeWindowAssociation(hwnd, DXGI_MWA_NO_ALT_ENTER);
    ComPtr<IDXGISwapChain3> sc;
    sc1.As(&sc);

    // Windows HDR must be on for this output, or the PQ codes would be shown as SDR.
    ComPtr<IDXGIOutput> out;
    ComPtr<IDXGIOutput6> out6;
    DXGI_OUTPUT_DESC1 od{};
    if (SUCCEEDED(sc->GetContainingOutput(&out)) && SUCCEEDED(out.As(&out6))) out6->GetDesc1(&od);
    if (od.ColorSpace != DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020) {
        printf("ERROR Windows HDR is off for this display (output colour space %d); turn on Use HDR\n",
               (int)od.ColorSpace);
        fflush(stdout);
        return 2;
    }
    UINT support = 0;
    sc->CheckColorSpaceSupport(DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020, &support);
    if (!(support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT))
        return Fail("swapchain does not support HDR10 colour space", E_FAIL);
    hr = sc->SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);
    if (FAILED(hr)) return Fail("SetColorSpace1", hr);

    ComPtr<ID3D11Texture2D> bb;
    sc->GetBuffer(0, IID_PPV_ARGS(&bb));
    ComPtr<ID3D11RenderTargetView> rtv;
    dev->CreateRenderTargetView(bb.Get(), nullptr, &rtv);

    printf("READY hdr=1 composed=%d w=%d h=%d display_min=%.4f display_max=%.1f display_maxfull=%.1f\n", composed ? 1 : 0, W,
           H, od.MinLuminance, od.MaxLuminance, od.MaxFullFrameLuminance);
    fflush(stdout);

    std::thread(Reader).detach();

    double patch[3] = {0, 0, 0}, bg = 0, area = 0.1;  // normalized PQ codes (R, G, B)
    bool perChannel = false;
    long shownId = 0;
    int holdFrames = -1;
    while (!g_quit) {
        MSG msg;
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        Command c;
        {
            std::lock_guard<std::mutex> g(g_lock);
            c = g_pending;
        }
        if (c.id != shownId) {
            shownId = c.id;
            if (c.op == 'N' || c.op == 'P') {
                const double v = c.op == 'N' ? PqFromNits(c.value) : std::min(std::max(c.value, 0.0), 1.0);
                patch[0] = patch[1] = patch[2] = v;
                area = c.area;
                perChannel = false;
            } else if (c.op == 'C') {
                for (int i = 0; i < 3; ++i) patch[i] = std::min(std::max(c.rgb[i], 0.0), 1023.0) / 1023.0;
                area = c.area;
                perChannel = true;
            }
            else if (c.op == 'B') { bg = PqFromNits(c.value); }
            holdFrames = 4;  // reply after the new frame has been on screen for a few vsyncs
        }
        // Quantize to the 10-bit code actually sent, so the reply states it exactly.
        long q[3];
        float pc[4] = {0, 0, 0, 1.0f};
        for (int i = 0; i < 3; ++i) {
            q[i] = std::lround(patch[i] * 1023.0);
            pc[i] = (float)(q[i] / 1023.0);
        }
        const float b10 = (float)(std::lround(bg * 1023.0) / 1023.0);
        // D3D11: buffer 0 is always the current back buffer (the runtime rotates flip-model buffers).
        const float bgc[4] = {b10, b10, b10, 1.0f};
        ctx->ClearRenderTargetView(rtv.Get(), bgc);
        const double side = std::sqrt(std::min(std::max(area, 0.001), 1.0));
        const LONG pw = (LONG)std::lround(W * side), ph = (LONG)std::lround(H * side);
        D3D11_RECT r{(W - pw) / 2, (H - ph) / 2, (W + pw) / 2, (H + ph) / 2};
        ctx->ClearView(rtv.Get(), pc, &r, 1);
        sc->Present(1, 0);
        if (holdFrames > 0 && --holdFrames == 0) {
            if (perChannel) printf("OK %ld %ld %ld\n", q[0], q[1], q[2]);
            else printf("OK %.6f %ld\n", patch[0], q[0]);
            fflush(stdout);
            holdFrames = -1;
        }
    }
    DestroyWindow(hwnd);
    return 0;
}
