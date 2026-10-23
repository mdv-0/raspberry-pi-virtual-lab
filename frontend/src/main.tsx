import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Check,
  Copy,
  Cpu,
  HardDrive,
  LayoutDashboard,
  Monitor,
  Moon,
  Sun,
  Network,
  Plug,
  Power,
  RotateCcw,
  TerminalSquare,
  Unplug,
  Usb,
  Zap,
} from "lucide-react";
import { BootSettings, StorageImport } from "./Storage";
import { Board } from "./Board";
import { active, type Status } from "./types";
import "./style.css";
function CopyCommand({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="command"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      title="Copy command"
    >
      <code>{value}</code>
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}
function App() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "light" ? "#f6f7f9" : "#0b0d12");
    try {
      localStorage.setItem("rpi-lab-theme", theme);
    } catch {
      /* Storage may be unavailable. */
    }
  }, [theme]);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("uart0");
  const [view, setView] = useState<"workspace" | "storage">("workspace");
  const [inspect, setInspect] = useState("");
  const [diskName, setDiskName] = useState("Student workspace");
  const [confirm, setConfirm] = useState<{
    label: string;
    path: string;
    method?: string;
  } | null>(null);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/status");
      if (!response.ok) throw new Error("Backend unavailable");
      setStatus(await response.json());
    } catch (e) {
      setError(String(e));
    }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, [refresh]);
  const action = async (path: string, body?: unknown, method = "POST") => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Operation failed");
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  if (!status)
    return (
      <main className="loading">
        <Cpu size={36} />
        <h1>Raspberry Pi Virtual Lab</h1>
        <p>{error || "Connecting to the local laboratory…"}</p>
        <button onClick={refresh}>Retry connection</button>
      </main>
    );
  const running = active(status.power);
  const disk = status.media.find((m) => m.state !== "AVAILABLE");
  const peripheral = status.peripherals.find((p) => p.id === selected)!;
  const icon = (id: string) =>
    id === "uart0" ? (
      <Usb size={18} />
    ) : id === "net0" ? (
      <Network size={18} />
    ) : id === "boot0" ? (
      <HardDrive size={18} />
    ) : (
      <Monitor size={18} />
    );
  const storage = (
    <>
      <div className="create-disk">
        <input
          aria-label="Disk name"
          value={diskName}
          onChange={(e) => setDiskName(e.target.value)}
          maxLength={80}
        />
        <button
          disabled={busy || running || !diskName.trim()}
          onClick={() => action("media", { name: diskName })}
        >
          <span>+</span> Create disk
        </button>
      </div>
      <div className="disk-list">
        {status.media.length === 0 ? (
          <div className="empty">
            <HardDrive size={28} />
            <p>No boot media yet</p>
            <span>Create a writable copy of the Alpine base image.</span>
          </div>
        ) : (
          status.media.map((m) => (
            <div className="disk" key={m.id}>
              <div className="disk-title">
                <HardDrive size={19} />
                <strong>{m.name}</strong>
                <span
                  className={`tag ${m.state !== "AVAILABLE" ? "green-tag" : ""}`}
                >
                  {m.state.replaceAll("_", " ")}
                </span>
              </div>
              <div className="button-row">
                <button
                  disabled={busy || running}
                  onClick={() =>
                    action(
                      m.state === "AVAILABLE"
                        ? `media/${m.id}/insert`
                        : "media/eject",
                    )
                  }
                >
                  {m.state === "AVAILABLE" ? "Insert" : "Eject"}
                </button>
                <button
                  onClick={async () => {
                    const r = await fetch(`/api/media/${m.id}/inspect`);
                    setInspect(JSON.stringify(await r.json(), null, 2));
                  }}
                >
                  Inspect
                </button>
                <button
                  disabled={busy || running}
                  onClick={() =>
                    setConfirm({
                      label: `Reset “${m.name}” and discard its saved changes?`,
                      path: `media/${m.id}/reset`,
                    })
                  }
                >
                  <RotateCcw size={12} />
                  Reset
                </button>
                <button
                  className="danger-text"
                  disabled={busy || running || m.state !== "AVAILABLE"}
                  title={
                    m.state !== "AVAILABLE"
                      ? "Eject this image before deleting"
                      : "Delete image"
                  }
                  onClick={() =>
                    setConfirm({
                      label: `Delete “${m.name}” and all its saved data?`,
                      path: `media/${m.id}`,
                      method: "DELETE",
                    })
                  }
                >
                  Delete
                </button>
              </div>
              <BootSettings
                key={`${m.id}-${m.boot.cmdline}-${m.boot.kernel}`}
                media={m}
                disabled={busy || running}
                save={action}
              />
            </div>
          ))
        )}
      </div>
      <StorageImport
        disabled={busy || running}
        refresh={refresh}
        fail={setError}
      />
    </>
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("workspace");
          }}
        >
          <span className="brand-icon">
            <Cpu size={20} />
          </span>
          <span>Virtual Lab</span>
        </a>
        <nav aria-label="Main navigation">
          <button
            className={view === "workspace" ? "nav-active" : ""}
            onClick={() => setView("workspace")}
          >
            <LayoutDashboard size={16} />
            Workspace
          </button>
          <button
            className={view === "storage" ? "nav-active" : ""}
            onClick={() => setView("storage")}
          >
            <HardDrive size={16} />
            Storage images<span>{status.media.length}</span>
          </button>
        </nav>
        <div className="header-actions">
          <button
            className="theme-toggle"
            aria-label={
              theme === "dark"
                ? "Switch to light theme"
                : "Switch to dark theme"
            }
            title={
              theme === "dark"
                ? "Switch to light theme"
                : "Switch to dark theme"
            }
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <main className="content">
          <div className="page-title">
            <div>
              <h1>
                {view === "workspace" ? "Board workspace" : "Storage images"}
              </h1>
            </div>
          </div>
          {(error || status.error) && (
            <div role="alert" className="error-banner">
              {error || status.error}
              <button onClick={() => setError("")}>×</button>
            </div>
          )}
          {view === "workspace" ? (
            <>
              <div className="workspace-grid">
                <section className="board-panel">
                  <div className="board-top">
                    <span
                      className={`power-badge ${running ? "on" : ""}`}
                      data-testid="power-state"
                    >
                      <span className={`dot ${running ? "green" : ""}`} />
                      {status.power}
                    </span>
                  </div>
                  <div className="board-canvas">
                    <Board
                      status={status}
                      selected={selected}
                      select={setSelected}
                    />
                  </div>
                  <div className="power-controls">
                    <div className="button-row">
                      <button
                        className="primary"
                        disabled={
                          busy ||
                          (running
                            ? status.power !== "RUNNING" ||
                              !status.network.link ||
                              !!disk?.boot.profile
                            : false)
                        }
                        title={
                          running && disk?.boot.profile
                            ? "Run sudo poweroff inside your guest using the VS Code terminal"
                            : running && !status.network.link
                              ? "Reconnect Ethernet for graceful shutdown"
                              : undefined
                        }
                        onClick={() => {
                          if (!running && !disk) {
                            setView("storage");
                            return;
                          }
                          void action(
                            status.power === "RUNNING"
                              ? "power/shutdown"
                              : "power/on",
                          );
                        }}
                      >
                        <Power size={15} />
                        {status.power === "STOPPING"
                          ? "Shutting down…"
                          : status.power === "STARTING"
                            ? "Starting…"
                            : status.power === "RUNNING"
                              ? "Shut down"
                              : !disk
                                ? "Select boot image"
                                : "Power on"}
                      </button>
                      <button
                        title="Hardware reset may lose unflushed data"
                        disabled={busy || status.power !== "RUNNING"}
                        onClick={() =>
                          setConfirm({
                            label:
                              "Reset the running board? Unflushed writes may be lost.",
                            path: "power/reset",
                          })
                        }
                      >
                        <RotateCcw size={14} />
                        Reset
                      </button>
                    </div>
                    <button
                      className="danger-text"
                      disabled={busy || !running}
                      onClick={() =>
                        setConfirm({
                          label:
                            "Force power off? This interrupts Linux and can corrupt the writable disk.",
                          path: "power/off",
                        })
                      }
                    >
                      <Zap size={14} />
                      Force off
                    </button>
                  </div>
                </section>
                <aside className="inspector">
                  <div className="device-heading">
                    <span className="device-icon">{icon(selected)}</span>
                    <div>
                      <h2>{peripheral.display_name}</h2>
                    </div>
                  </div>

                  {selected === "uart0" ? (
                    <>
                      <div className="property">
                        <span>Connection</span>
                        <strong
                          className={
                            status.uart.mode !== "disconnected"
                              ? "green-text"
                              : ""
                          }
                        >
                          {status.uart.mode === "disconnected"
                            ? "Disconnected"
                            : status.uart.mode === "host"
                              ? "Host terminal"
                              : "Disconnected"}
                        </strong>
                      </div>
                      <div className="inspector-actions">
                        <button
                          className="primary full"
                          disabled={busy || status.uart.mode === "host"}
                          onClick={() => action("uart", { mode: "host" })}
                        >
                          <Plug size={14} />
                          {status.uart.mode === "host"
                            ? "Host connected"
                            : "Connect to host"}
                        </button>
                        <button
                          className="full"
                          disabled={busy || status.uart.mode === "disconnected"}
                          onClick={() =>
                            action("uart", { mode: "disconnected" })
                          }
                        >
                          <Unplug size={14} />
                          Disconnect UART
                        </button>
                      </div>
                      {status.uart.endpoint && (
                        <div className="endpoint">
                          <div className="field-label">HOST DEVICE PATH</div>
                          <code data-testid="uart-endpoint">
                            {status.uart.endpoint}
                          </code>
                        </div>
                      )}
                    </>
                  ) : selected === "net0" ? (
                    <>
                      <div className="property">
                        <span>Link</span>
                        <strong>
                          {status.network.link ? "Connected" : "Disconnected"}
                        </strong>
                      </div>
                      <button
                        className="primary full"
                        disabled={busy}
                        onClick={() =>
                          action("network", { up: !status.network.link })
                        }
                      >
                        {status.network.link ? (
                          <Unplug size={14} />
                        ) : (
                          <Plug size={14} />
                        )}{" "}
                        {status.network.link
                          ? "Disconnect Ethernet"
                          : "Connect Ethernet"}
                      </button>
                      <CopyCommand value={status.network.ssh} />
                      <p className="small muted">
                        {disk?.boot.profile
                          ? "Use the login configured in your image. Shut down with sudo poweroff inside the guest."
                          : "Login: student / student."}
                      </p>
                    </>
                  ) : selected === "boot0" ? (
                    <>
                      <div className="property">
                        <span>Inserted image</span>
                        <strong>{disk?.name || "None"}</strong>
                      </div>
                      <button
                        className="primary full"
                        onClick={() => setView("storage")}
                      >
                        <HardDrive size={14} />
                        Manage storage
                      </button>
                      <button
                        className="full"
                        disabled={busy || running || !disk}
                        onClick={() => action("media/eject")}
                      >
                        Eject boot media
                      </button>
                    </>
                  ) : selected === "display0" ? (
                    <>
                      <div className="property">
                        <span>Video adapter</span>
                        <strong>virtio-gpu</strong>
                      </div>
                      <div className="property">
                        <span>Keyboard</span>
                        <strong>virtio keyboard</strong>
                      </div>
                      <div className="property">
                        <span>Resolution</span>
                        <strong>{status.display.resolution}</strong>
                      </div>
                      <p className="small muted">
                        In-browser console viewing is disabled. Use the terminal
                        in VS Code for UART or SSH.
                      </p>
                    </>
                  ) : (
                    <div className="unsupported">
                      <Monitor size={28} />
                      <strong>Not available for this profile</strong>
                      <p>
                        This connector has no implemented backend operation.
                      </p>
                    </div>
                  )}
                  <details className="device-details">
                    <summary>About this device</summary>
                    <p>{peripheral.limitation}</p>
                    {selected === "uart0" && <p>115200 · 8N1 · /dev/ttyAMA0</p>}
                    <span>{peripheral.category}</span>
                  </details>
                </aside>
              </div>
              <section className="host-access">
                <h2>Terminal access</h2>
                <p>
                  {disk?.boot.profile
                    ? "Use your image's login. Shut down from the VS Code terminal."
                    : "VS Code terminal · student / student"}
                </p>
                <div className="access-row">
                  <div>
                    <TerminalSquare size={16} />
                    <span>UART</span>
                  </div>
                  <CopyCommand value={status.commands.uart} />
                  <div>
                    <Network size={16} />
                    <span>SSH</span>
                  </div>
                  <CopyCommand value={status.network.ssh} />
                </div>
              </section>
            </>
          ) : (
            <section className="standalone-panel">{storage}</section>
          )}
        </main>
      </div>
      {confirm && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Confirm operation"
          >
            <Zap size={25} />
            <h2>{confirm.label}</h2>
            <div className="button-row">
              <button onClick={() => setConfirm(null)}>Cancel</button>
              <button
                className="danger"
                onClick={() => {
                  action(confirm.path, undefined, confirm.method);
                  setConfirm(null);
                }}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}
      {inspect && (
        <div className="modal-backdrop">
          <div className="modal wide" role="dialog" aria-label="Image metadata">
            <h2>Image metadata</h2>
            <pre>{inspect}</pre>
            <button onClick={() => setInspect("")}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
