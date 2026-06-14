const TW_DIGITAL_SRCDOC = (function () {
  try {
    const b64 = (window as Window & { __DIGITAL_TWIN_B64?: string }).__DIGITAL_TWIN_B64;
    if (!b64) return null;
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  } catch {
    return null;
  }
})();

export default function TwinDigitalDemoPage() {
  return (
    <>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {TW_DIGITAL_SRCDOC ? (
          <iframe
            className="tw-digi-demo-frame"
            srcDoc={TW_DIGITAL_SRCDOC}
            title="数字孪生 · 预制演示"
          />
        ) : (
          <iframe
            className="tw-digi-demo-frame"
            src="/twin/digital-twin.html?instant=1&v=okl7"
            title="数字孪生 · 预制演示"
          />
        )}
      </div>
      <style>{`.tw-digi-demo-frame{width:100%;height:100%;border:0;display:block;background:transparent}`}</style>
    </>
  );
}
