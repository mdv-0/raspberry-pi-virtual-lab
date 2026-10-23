import { useState } from "react";
import { ArrowUpRight, Settings2 } from "lucide-react";
import type { Media } from "./types";

export function StorageImport({
  disabled,
  refresh,
  fail,
}: {
  disabled: boolean;
  refresh: () => Promise<void>;
  fail: (error: string) => void;
}) {
  const [profile, setProfile] = useState("virt-arm64");
  const [path, setPath] = useState("");
  const [pending, setPending] = useState(false);
  async function upload(file?: File) {
    setPending(true);
    fail("");
    try {
      const response = await fetch(
        file
          ? `/api/media/import?profile=${profile}&name=${encodeURIComponent(file.name)}`
          : "/api/media/import-path",
        file
          ? {
              method: "POST",
              body: file,
            }
          : {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path, profile }),
            },
      );
      if (!response.ok) throw new Error((await response.json()).detail);
      await refresh();
    } catch (error) {
      fail(String(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <details className="storage-import">
      <summary>
        <ArrowUpRight size={14} /> Import disk image
      </summary>
      <p className="muted small">
        Raw .img, .wic, .sdimg or .ext4 · MBR / GPT · up to 64 GiB. Decompress
        archives first. Imports are independent copies.
      </p>
      <label className="storage-field">
        Target board
        <select
          aria-label="Target board"
          value={profile}
          disabled={disabled || pending}
          onChange={(e) => setProfile(e.target.value)}
        >
          <option value="virt-arm64">ARM64 virt — Yocto / Buildroot</option>
          <option value="raspi3b">Raspberry Pi 3B — 64-bit SD image</option>
        </select>
      </label>
      <p className="muted small">
        {profile === "raspi3b"
          ? "Extracts kernel8.img, the Pi 3B DTB and optional initramfs8 from the FAT boot partition. Firmware settings and overlays are not applied. Pi 4/5-only and 32-bit images are incompatible."
          : "Build for QEMU virt / AArch64. After import, configure your kernel, optional initramfs / DTB and Linux command line."}
      </p>
      <form
        className="import-path"
        onSubmit={(e) => {
          e.preventDefault();
          void upload();
        }}
      >
        <input
          aria-label="Image path on host"
          placeholder="/home/user/build/output/images/sdcard.img"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          disabled={disabled || pending}
        />
        <button disabled={disabled || pending || !path.trim()}>
          {pending ? "Importing…" : "Import from path"}
        </button>
      </form>
      <label
        className={`import-button ${disabled || pending ? "disabled" : ""}`}
      >
        Or choose a file
        <input
          type="file"
          accept=".raw,.img,.wic,.sdimg,.ext4"
          disabled={disabled || pending}
          onChange={(e) => {
            const file = e.currentTarget.files?.[0];
            e.currentTarget.value = "";
            if (file) void upload(file);
          }}
        />
      </label>
    </details>
  );
}

export function BootSettings({
  media,
  disabled,
  save,
}: {
  media: Media;
  disabled: boolean;
  save: (path: string, body?: unknown) => Promise<void>;
}) {
  const [kernel, setKernel] = useState("");
  const [initrd, setInitrd] = useState("");
  const [dtb, setDtb] = useState("");
  const [clearInitrd, setClearInitrd] = useState(false);
  const [clearDtb, setClearDtb] = useState(false);
  const [cmdline, setCmdline] = useState(
    media.boot.cmdline || "console=ttyAMA0,115200 root=/dev/vda rw",
  );
  return (
    <details className="boot-settings">
      <summary>
        <Settings2 size={13} /> Boot settings
        {media.boot.profile && !media.boot.kernel ? " · kernel required" : ""}
      </summary>
      <p className="muted small">
        {media.boot.profile === "raspi3b" ? "Raspberry Pi 3B" : "ARM64 virt"}.
        Host paths are copied when saved. Empty fields keep existing files. Use
        the guest's own login credentials and poweroff command.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save(`media/${media.id}/boot`, {
            profile: media.boot.profile || "virt-arm64",
            kernel_path: kernel,
            initrd_path: initrd,
            dtb_path: dtb,
            cmdline,
            clear_initrd: clearInitrd,
            clear_dtb: clearDtb,
          });
        }}
      >
        {[
          {
            label: "Kernel",
            value: kernel,
            set: setKernel,
            current: media.boot.kernel,
          },
          {
            label: "Initramfs (optional)",
            value: initrd,
            set: setInitrd,
            current: media.boot.initrd,
          },
          {
            label: "DTB (optional on virt)",
            value: dtb,
            set: setDtb,
            current: media.boot.dtb,
          },
        ].map((field) => (
          <label className="storage-field" key={field.label}>
            {field.label}
            <input
              aria-label={`${field.label} path for ${media.name}`}
              placeholder={
                field.current
                  ? "Current file saved · enter path to replace"
                  : "/absolute/path/on/host"
              }
              value={field.value}
              disabled={disabled}
              onChange={(e) => field.set(e.target.value)}
            />
            {field.current && (
              <span className="artifact-name">
                Saved: {field.current.split("/").at(-1)}
              </span>
            )}
          </label>
        ))}
        <div className="button-row">
          <label>
            <input
              type="checkbox"
              checked={clearInitrd}
              disabled={disabled || !!initrd}
              onChange={(e) => setClearInitrd(e.target.checked)}
            />{" "}
            No initramfs
          </label>
          {media.boot.profile !== "raspi3b" && (
            <label>
              <input
                type="checkbox"
                checked={clearDtb}
                disabled={disabled || !!dtb}
                onChange={(e) => setClearDtb(e.target.checked)}
              />{" "}
              Use QEMU DTB
            </label>
          )}
        </div>
        <label className="storage-field">
          Linux command line
          <textarea
            aria-label={`Linux command line for ${media.name}`}
            rows={3}
            value={cmdline}
            disabled={disabled}
            onChange={(e) => setCmdline(e.target.value)}
            required
            maxLength={4096}
          />
        </label>
        <button disabled={disabled || !cmdline.trim()}>
          Save boot settings
        </button>
      </form>
    </details>
  );
}
